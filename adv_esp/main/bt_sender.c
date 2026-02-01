// bt_sender.c
#include "bt_sender.h"
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_bt.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "bt_hci_common.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"

#define TX_OFFSET_US 9000 // Estimated time offset for TX in microseconds based on empirical measurements
#define MAX_ACTIVE_TASKS 4
#ifndef HCI_GRP_HOST_CONT_BASEBAND_CMDS
#define HCI_GRP_HOST_CONT_BASEBAND_CMDS (0x03 << 10)
#endif

#ifndef HCI_GRP_BLE_CMDS
#define HCI_GRP_BLE_CMDS               (0x08 << 10)
#endif

#ifndef HCI_SET_EVT_MASK
#define HCI_SET_EVT_MASK               (0x0001 | HCI_GRP_HOST_CONT_BASEBAND_CMDS)
#endif

#ifndef HCI_BLE_WRITE_SCAN_PARAM
#define HCI_BLE_WRITE_SCAN_PARAM       (0x000B | HCI_GRP_BLE_CMDS)
#endif
#ifndef HCI_BLE_WRITE_SCAN_ENABLE
#define HCI_BLE_WRITE_SCAN_ENABLE      (0x000C | HCI_GRP_BLE_CMDS)
#endif
#ifndef HCIC_PARAM_SIZE_SET_EVENT_MASK
#define HCIC_PARAM_SIZE_SET_EVENT_MASK         (8)
#endif
static const char *TAG = "BT_SENDER";
static volatile int64_t last_measured_latency = 0;
static int64_t t1_start = 0;
static uint8_t hci_cmd_buf[128];
static bool is_initialized = false;
static bool is_checking = false;
typedef struct {
    bool active;
    int64_t end_time_us;
    bt_sender_config_t config;
} active_task_t;
static active_task_t s_tasks[MAX_ACTIVE_TASKS];
static SemaphoreHandle_t s_task_mutex = NULL;
static int s_rr_index = 0; // Round-Robin Index
// Helper functions to send HCI commands
static void hci_cmd_send_ble_set_adv_data(uint8_t cmd_type, uint32_t delay_us, uint32_t prep_led_us, uint64_t target_mask,const uint8_t *data) {
    uint8_t raw_adv_data[31];
    uint8_t idx = 0;
    
    // Flags
    raw_adv_data[idx++] = 2; raw_adv_data[idx++] = 0x01; raw_adv_data[idx++] = 0x06;
    
    // Manufacturer Specific Data
    raw_adv_data[idx++] = 20; // len
    raw_adv_data[idx++] = 0xFF; raw_adv_data[idx++] = 0xFF; raw_adv_data[idx++] = 0xFF;
    raw_adv_data[idx++] = cmd_type;

    // Bitmask for player ID (8 bytes)
    raw_adv_data[idx++] = (uint8_t)(target_mask & 0xFF);         // IDs 0-7
    raw_adv_data[idx++] = (uint8_t)((target_mask >> 8) & 0xFF);  // IDs 8-15
    raw_adv_data[idx++] = (uint8_t)((target_mask >> 16) & 0xFF); // IDs 16-23
    raw_adv_data[idx++] = (uint8_t)((target_mask >> 24) & 0xFF); // IDs 24-31
    raw_adv_data[idx++] = (uint8_t)((target_mask >> 32) & 0xFF); // IDs 32-39
    raw_adv_data[idx++] = (uint8_t)((target_mask >> 40) & 0xFF); // IDs 40-47
    raw_adv_data[idx++] = (uint8_t)((target_mask >> 48) & 0xFF); // IDs 48-55
    raw_adv_data[idx++] = (uint8_t)((target_mask >> 56) & 0xFF); // IDs 56-63

    // Delay info (4 bytes)
    raw_adv_data[idx++] = (delay_us >> 24) & 0xFF;
    raw_adv_data[idx++] = (delay_us >> 16) & 0xFF;
    raw_adv_data[idx++] = (delay_us >> 8)  & 0xFF;
    raw_adv_data[idx++] = (delay_us)       & 0xFF;

    // Delay info (4 bytes)
    raw_adv_data[idx++] = (prep_led_us >> 24) & 0xFF;
    raw_adv_data[idx++] = (prep_led_us >> 16) & 0xFF;
    raw_adv_data[idx++] = (prep_led_us >> 8)  & 0xFF;
    raw_adv_data[idx++] = (prep_led_us)       & 0xFF;
    // rgb
    raw_adv_data[idx++] = data[0];
    raw_adv_data[idx++] = data[1];
    raw_adv_data[idx++] = data[2];

    uint16_t sz = make_cmd_ble_set_adv_data(hci_cmd_buf, idx, raw_adv_data);
    if (esp_vhci_host_check_send_available()) esp_vhci_host_send_packet(hci_cmd_buf, sz);
}

static void hci_cmd_send_ble_set_adv_param(void) {
    uint8_t peer_addr[6] = {0};
    uint16_t sz = make_cmd_ble_set_adv_param(hci_cmd_buf, 0x20, 0x20, 0x03, 0, 0, peer_addr, 0x07, 0);
    esp_vhci_host_send_packet(hci_cmd_buf, sz);
}

static void hci_cmd_send_ble_adv_start(void) {
    uint16_t sz = make_cmd_ble_set_adv_enable(hci_cmd_buf, 1);
    if (esp_vhci_host_check_send_available()) esp_vhci_host_send_packet(hci_cmd_buf, sz);
}

static void hci_cmd_send_ble_adv_stop(void) {
    uint16_t sz = make_cmd_ble_set_adv_enable(hci_cmd_buf, 0);
    if (esp_vhci_host_check_send_available()) esp_vhci_host_send_packet(hci_cmd_buf, sz);
}

static void hci_cmd_send_reset(void) {
    uint16_t sz = make_cmd_reset(hci_cmd_buf);
    esp_vhci_host_send_packet(hci_cmd_buf, sz);
}

static void controller_rcv_pkt_ready(void) {}
static int host_rcv_pkt(uint8_t *data, uint16_t len) {
    if(!is_checking) return ESP_OK;
    if(data[0] != 0x04 || data[1] != 0x3E || data[3] != 0x02) return ESP_OK;

    uint8_t num_reports = data[4];
    uint8_t* payload = &data[5];
    for(int i = 0; i < num_reports; i++) {
        uint8_t data_len = payload[8];
        uint8_t* adv_data = &payload[9];
        uint8_t offset = 0;
        while(offset < data_len) {
            uint8_t ad_len = adv_data[offset++];
            if(ad_len == 0) break;
            uint8_t ad_type = adv_data[offset++];

            if(ad_type == 0xFF && ad_len >= 8) { // Manuf Data
                 if(adv_data[offset] == 0xFF && adv_data[offset + 1] == 0xFF) {
                     // Check Type == 0x08 (ACK)
                     if (adv_data[offset+2] == 0x08) {
                         uint8_t target_id = adv_data[offset+3];
                         uint8_t cmd_id    = adv_data[offset+4];
                         uint8_t cmd_type  = adv_data[offset+5];
                         uint32_t delay    = (adv_data[offset+6] << 24) | (adv_data[offset+7] << 16) | (adv_data[offset+8] << 8) | adv_data[offset+9];
                         uint8_t state = adv_data[offset+10];
                         printf("FOUND:%d,%d,%d,%lu,%d\n", target_id, cmd_id, cmd_type, delay, state);
                     }
                 }
            }
            offset += (ad_len - 1);
        }
        payload += (10 + data_len + 1);
    }
    return ESP_OK;
}
static esp_vhci_host_callback_t vhci_host_cb = { controller_rcv_pkt_ready, host_rcv_pkt };
static void hci_cmd_send_set_event_mask(void) {
    uint8_t buf[128];
    uint8_t *p = buf;
    
    // receive LE Meta Event (Bit 61)
    // Mask: 00 00 00 00 00 00 00 20
    uint8_t mask[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x20};

    // HCI Command (Opcode: 0x0C01)
    *p++ = 0x01; // HCI_COMMAND_PKT
    *p++ = 0x01; // Opcode LSB (0x01)
    *p++ = 0x0C; // Opcode MSB (0x0C) -> 0x0C01 (Set Event Mask)
    *p++ = 0x08; // Param Len
    memcpy(p, mask, 8);
    
    esp_vhci_host_send_packet(buf, 4 + 8);
}
static void broadcast_scheduler_task(void *arg) {
    ESP_LOGI(TAG, "Broadcast Scheduler Started (20ms cycle)");
    
    while (1) {
        if (is_checking) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        int64_t now_us = esp_timer_get_time();
        int active_count = 0;
        int task_index_to_run = -1;

        xSemaphoreTake(s_task_mutex, portMAX_DELAY);
        for (int i = 0; i < MAX_ACTIVE_TASKS; i++) {
            if (s_tasks[i].active) {
                if (now_us >= s_tasks[i].end_time_us) {
                    s_tasks[i].active = false;
                } else {
                    active_count++;
                }
            }
        }
        if (active_count > 0) {
            for (int k = 0; k < MAX_ACTIVE_TASKS; k++) {
                int idx = (s_rr_index + k) % MAX_ACTIVE_TASKS;
                if (s_tasks[idx].active) {
                    task_index_to_run = idx;
                    s_rr_index = (idx + 1) % MAX_ACTIVE_TASKS;
                    break;
                }
            }
        }
        xSemaphoreGive(s_task_mutex);
        if (task_index_to_run != -1) {
            active_task_t *t = &s_tasks[task_index_to_run];
            int32_t remain = (int32_t)(t->end_time_us - now_us - TX_OFFSET_US);
            if (remain < 0) remain = 0;

            // Set Data -> Start -> Delay -> Stop
            hci_cmd_send_ble_set_adv_data(t->config.cmd_type, remain, t->config.prep_led_us, t->config.target_mask, t->config.data);
            esp_rom_delay_us(500); 
            hci_cmd_send_ble_adv_start();
            // advertise 10ms
            vTaskDelay(pdMS_TO_TICKS(10)); 
            hci_cmd_send_ble_adv_stop();
        }
        vTaskDelay(pdMS_TO_TICKS(10)); 
    }
}
esp_err_t bt_sender_init(void) {
    if (is_initialized) return ESP_OK;

    // NVS Initialization
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Controller Initialization
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
    esp_bt_controller_init(&bt_cfg);
    esp_bt_controller_enable(ESP_BT_MODE_BLE);
    esp_vhci_host_register_callback(&vhci_host_cb);

    vTaskDelay(1000 / portTICK_PERIOD_MS);

    // HCI Commands Initialization
    hci_cmd_send_reset();
    vTaskDelay(100 / portTICK_PERIOD_MS);
    hci_cmd_send_set_event_mask();
    hci_cmd_send_ble_set_adv_param();
    vTaskDelay(100 / portTICK_PERIOD_MS);
    s_task_mutex = xSemaphoreCreateMutex();
    for(int i=0; i<MAX_ACTIVE_TASKS; i++) s_tasks[i].active = false;
    xTaskCreate(broadcast_scheduler_task, "bt_scheduler", 4096, NULL, 10, NULL);

    is_initialized = true;
    ESP_LOGI(TAG, "BT Sender API Initialized");
    return ESP_OK;
}
int bt_sender_add_task(const bt_sender_config_t *config) {
    if (!is_initialized) return 0;
    int slot = -1;
    xSemaphoreTake(s_task_mutex, portMAX_DELAY);
    for (int i = 0; i < MAX_ACTIVE_TASKS; i++) {
        if (!s_tasks[i].active) {
            slot = i;
            break;
        }
    }
    if (slot != -1) {
        s_tasks[slot].config = *config;
        s_tasks[slot].end_time_us = esp_timer_get_time() + config->delay_us;
        s_tasks[slot].active = true;
        ESP_LOGD(TAG, "Task added to slot %d (Type 0x%02X)", slot, config->cmd_type);
    } else {
        ESP_LOGW(TAG, "Task List Full! Dropping CMD 0x%02X", config->cmd_type);
    }
    xSemaphoreGive(s_task_mutex);
    return (slot != -1) ? 1 : 0;
}
void bt_sender_start_check(uint32_t duration_ms) {
    if (!is_initialized) return;

    is_checking = true;

    hci_cmd_send_ble_adv_stop();
    vTaskDelay(pdMS_TO_TICKS(20));

    // Scan Interval 100ms, Window 100ms
    uint8_t buf[128];
    make_cmd_ble_set_scan_params(buf, 0, 0x00A0, 0x00A0, 0, 0); 
    esp_vhci_host_send_packet(buf, 7 + 4); // param size adjustment needed
    vTaskDelay(pdMS_TO_TICKS(20));

    make_cmd_ble_set_scan_enable(buf, 1, 0);
    esp_vhci_host_send_packet(buf, 2 + 4);

    vTaskDelay(pdMS_TO_TICKS(duration_ms));

    make_cmd_ble_set_scan_enable(buf, 0, 0);
    esp_vhci_host_send_packet(buf, 2 + 4);

    is_checking = false;
    printf("CHECK_DONE\n");
}