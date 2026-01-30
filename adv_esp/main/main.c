#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "bt_sender.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_timer.h"

static const char *TAG = "UART_SIMPLE";

#define UART_PORT_NUM      UART_NUM_0
#define BUF_SIZE           1024
#define TXD_PIN            UART_PIN_NO_CHANGE
#define RXD_PIN            UART_PIN_NO_CHANGE

static char packet_buf[128];
static int packet_idx = 0;

static QueueHandle_t uart0_queue;

void process_byte(uint8_t c, int64_t t_wake, int64_t t_read_done) {
    if (c == '\n') {
        packet_buf[packet_idx] = '\0';
        if (strncmp(packet_buf, "CHECK", 5) == 0) {
            uart_write_bytes(UART_PORT_NUM, "ACK:CHECK_START\n", 16);
            //2000 or 4000(OK)?
            bt_sender_start_check(2000); 
            
        }
        else{
            // cmd,delay,hex_mask        
            int cmd_in = 0;
            unsigned long delay_us = 0;
            unsigned long prep_led_us = 0;
            unsigned long long target_mask = 0;
            int in_data[3];

            int args = sscanf(packet_buf, "%d,%lu,%lu,%llx,%d,%d,%d", &cmd_in, &delay_us, &prep_led_us, &target_mask, &in_data[0], &in_data[1], &in_data[2]);

            if (args == 7) {
                int64_t t_parse_done = esp_timer_get_time();

                int64_t d_read  = t_read_done - t_wake;
                int64_t d_parse = t_parse_done - t_read_done;
                int64_t d_total = t_parse_done - t_wake;

                char ack_msg[64];
                snprintf(ack_msg, sizeof(ack_msg), "ACK:OK:%lld:%lld:%lld\n", d_read, d_parse, d_total);
                uart_write_bytes(UART_PORT_NUM, ack_msg, strlen(ack_msg));
                bt_sender_config_t burst_cfg = {
                    .cmd_type = (uint8_t)cmd_in,
                    .delay_us = delay_us,
                    .prep_led_us = prep_led_us,
                    .target_mask = (uint64_t)target_mask,
                    .data[0]=(uint8_t)in_data[0],
                    .data[1]=(uint8_t)in_data[1],
                    .data[2]=(uint8_t)in_data[2]
                };
                bt_sender_execute_burst(&burst_cfg);
                uart_write_bytes(UART_PORT_NUM, "DONE\n", 5);
                // bt_sender_start_check(2000);
            } else {
                uart_write_bytes(UART_PORT_NUM, "NAK:ParseError\n", 15);
            }
            
        }
        packet_idx = 0;
    } 
    else if (c == '\r') {
        // neglect
    }
    else if (packet_idx < sizeof(packet_buf) - 1) {
        packet_buf[packet_idx++] = (char)c;
    } 
    else {
        packet_idx = 0;
        uart_write_bytes(UART_PORT_NUM, "NAK:Overflow\n", 13);
    }
}

static void uart_event_task(void *pvParameters)
{
    uart_event_t event;
    uint8_t* dtmp = (uint8_t*) malloc(BUF_SIZE);

    for(;;) {
        if(xQueueReceive(uart0_queue, (void * )&event, (TickType_t)portMAX_DELAY)) {
            // receive interrupt
            int64_t t_wake = esp_timer_get_time();
            switch(event.type) {
                case UART_DATA:
                    uart_read_bytes(UART_PORT_NUM, dtmp, event.size, 0);
                    int64_t t_read_done = esp_timer_get_time();
                    for (int i = 0; i < event.size; i++) {
                        process_byte(dtmp[i], t_wake, t_read_done);
                    }
                    break;
                case UART_FIFO_OVF:
                    ESP_LOGW(TAG, "hw fifo overflow");
                    uart_flush_input(UART_PORT_NUM);
                    xQueueReset(uart0_queue);
                    break;
                case UART_BUFFER_FULL:
                    ESP_LOGW(TAG, "ring buffer full");
                    uart_flush_input(UART_PORT_NUM);
                    xQueueReset(uart0_queue);
                    break;
                default:
                    ESP_LOGI(TAG, "uart event type: %d", event.type);
                    break;
            }
        }
    }
    free(dtmp);
    dtmp = NULL;
    vTaskDelete(NULL);
}

void app_main(void)
{
    if (bt_sender_init() != ESP_OK) return;
    uart_config_t uart_config = {
        .baud_rate = 921600,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    ESP_ERROR_CHECK(uart_param_config(UART_PORT_NUM, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(UART_PORT_NUM, TXD_PIN, RXD_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_driver_install(UART_PORT_NUM, BUF_SIZE * 2, BUF_SIZE * 2, 20, &uart0_queue, 0));

    xTaskCreate(uart_event_task, "uart_event_task", 4096, NULL, 12, NULL);

    ESP_LOGI(TAG, "UART Listening...");

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}