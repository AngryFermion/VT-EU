/*
 * ancit_uart_esp.c
 *
 *  Created on: 18-May-2024
 *      Author: Narayan
 */
#include <ancit_driver_uart.h>
#include "ancit_uart_rte.h"
#include "genx_uart_rte.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#include "ancit_timer.h"
#include "genx_common.h"
#include "fota_uart.h"

#ifdef UART_RTE_CONFIGURED

// ── TX state ────────────────────────────────────────────────────────────────
ext_uart_tx_state_t current_state = ANCIT_UART_CONN_TX_IDLE;

static StringQueue txQueue;
static char currentString[MAX_STRING_LENGTH];
static uint8_t currentStringLength;

// ── RX state ────────────────────────────────────────────────────────────────
static uint8_t fota_rx_phase = 0;
static volatile uint8_t fota_rx_ready = 0;

// ── TX state machine ─────────────────────────────────────────────────────────
void ancit_uart_conn_sm(void) {
	static uint32_t bytesRemaining;

	switch (current_state) {
	case ANCIT_UART_CONN_TX_IDLE:
		if (!ancit_uart_conn_IsQueueEmpty()) {
			ancit_uart_conn_DequeueString(currentString, &currentStringLength);
			current_state = ANCIT_UART_CONN_TX_START;
		}
		break;

	case ANCIT_UART_CONN_TX_START:
		ancit_driver_uart_SendData(EXT_UART, (uint8_t*) currentString,
				currentStringLength);
		current_state = ANCIT_UART_CONN_TX_WAIT_FOR_COMPLETE;
		break;

	case ANCIT_UART_CONN_TX_WAIT_FOR_COMPLETE:
		if (ancit_driver_uart_GetTransmitStatus(EXT_UART, &bytesRemaining)
				!= STATUS_SUCCESS) {
			//wait till busy
		} else {
			current_state = ANCIT_UART_CONN_TX_COMPLETE;
		}
		break;

	case ANCIT_UART_CONN_TX_COMPLETE:
		current_state = ANCIT_UART_CONN_TX_DONE;
		break;

	case ANCIT_UART_CONN_TX_DONE:
		current_state = ANCIT_UART_CONN_TX_IDLE;
		break;
	}
}

// ── RX byte callback (called from LPUART ISR) ─────────────────────────────
void ancit_uart_rx_byte_cb(void *driverState, uart_event_t event, void *param) {

	(void)driverState;
	(void)param;

	if (event == UART_EVENT_RX_FULL) {
		if (fota_rx_phase == 0) {
			if (UartData.rx_data[1] == TYPE_0 || UartData.rx_data[1] == TYPE_5) {
				fota_rx_ready = 1;
				ancit_driver_uart_ReceiveData(EXT_UART, &UartData.rx_data[0], 2);
			} else {
				fota_rx_phase = 1;
				ancit_driver_uart_ReceiveData(EXT_UART, &UartData.rx_data[2], UART_BUFF_LEN - 2);
			}
		} else {
			fota_rx_phase = 0;
			fota_rx_ready = 1;
			ancit_driver_uart_ReceiveData(EXT_UART, &UartData.rx_data[0], 2);
		}
	}

}

// ── Command dispatcher ────────────────────────────────────────────────────────
void ancit_uart_cmd_dispatch(const char *cmd) {
	ancit_uart_command_receive((char *)cmd);
}

// ── Queue helpers ─────────────────────────────────────────────────────────────
bool ancit_uart_conn_EnqueueString(const char *str, uint8_t length) {
	if (txQueue.count >= QUEUE_SIZE) {
		return false;
	}
	memcpy(txQueue.buffer[txQueue.tail], str, length);
	txQueue.length[txQueue.tail] = length;
	txQueue.tail = (txQueue.tail + 1) % QUEUE_SIZE;
	txQueue.count++;
	return true;
}

void ancit_uart_conn_DequeueString(char *str, uint8_t *length) {
	if (txQueue.count > 0) {
		memcpy(str, txQueue.buffer[txQueue.head],
				txQueue.length[txQueue.head]);
		*length = txQueue.length[txQueue.head];
		txQueue.head = (txQueue.head + 1) % QUEUE_SIZE;
		txQueue.count--;
	}
}

bool ancit_uart_conn_IsQueueEmpty(void) {
	return txQueue.count == 0;
}

// ── Start / Main ──────────────────────────────────────────────────────────────
void ancit_uart_conn_start(void) {
	ancit_driver_uart_Init(EXT_UART, &lpUartState0, &lpuart_0_InitConfig0);
	current_state = ANCIT_UART_CONN_TX_IDLE;

	// Install RX callback and arm for first byte
	ancit_driver_uart_InstallRxCallback(EXT_UART, ancit_uart_rx_byte_cb, NULL);
	ancit_driver_uart_ReceiveData(EXT_UART, &UartData.rx_data[0], 2);

#ifdef DWIN_DISPLAY_CONFIGURED
	ancit_dwin_tx_start();
	ancit_dwin_rx_start();
#endif
}

void ancit_uart_conn_main(void) {
#ifdef DWIN_DISPLAY_CONFIGURED
	ancit_dwin_tx_main();
	ancit_dwin_rx_main();
#endif

	if (fota_rx_ready) {
		fota_rx_ready = 0;
		fota_pre_process();
		fota_process_data();
	}

	ancit_uart_conn_sm();
}

#endif //UART_RTE_CONFIGURED
