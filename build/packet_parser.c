#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    const uint8_t* data;
    size_t len;
} bytes;

typedef struct {
    uint8_t header_version;
    uint8_t header_flags;
    uint16_t header_reserved;
    uint32_t payload_len;
    uint32_t header_checksum;
    const bytes* payload;
    uint32_t payload_checksum;
} Packet;

typedef enum {
    TooShort,
    InvalidVersion,
    ChecksumMismatch,
    PayloadLengthMismatch,
    BufferOverflow
} ParseError;

typedef struct {
    bool is_ok;
    union {
        Packet value;
        ParseError error;
    };
} Result;

static uint32_t read_be32(const uint8_t* data) {
    return ((uint32_t)data[0] << 24) | 
           ((uint32_t)data[1] << 16) | 
           ((uint32_t)data[2] << 8) | 
           (uint32_t)data[3];
}

static uint16_t read_be16(const uint8_t* data) {
    return ((uint16_t)data[0] << 8) | (uint16_t)data[1];
}

static uint32_t calculate_checksum(const uint8_t* data, size_t len) {
    uint32_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum += data[i];
    }
    return sum;
}

Result parse_packet(const bytes* raw, size_t raw_len) {
    Result result = {0};
    
    if (raw_len < 1 || raw_len > 65535) {
        result.is_ok = false;
        result.error = TooShort;
        return result;
    }
    
    if (raw_len < 12) {
        result.is_ok = false;
        result.error = TooShort;
        return result;
    }
    
    uint8_t version = raw->data[0];
    if (version != 1 && version != 2) {
        result.is_ok = false;
        result.error = InvalidVersion;
        return result;
    }
    
    uint8_t flags = raw->data[1];
    uint16_t reserved = read_be16(&raw->data[2]);
    uint32_t payload_len = read_be32(&raw->data[4]);
    uint32_t header_checksum = read_be32(&raw->data[8]);
    
    uint32_t calculated_header_checksum = calculate_checksum(raw->data, 8);
    if (calculated_header_checksum != header_checksum) {
        result.is_ok = false;
        result.error = ChecksumMismatch;
        return result;
    }
    
    if (raw_len < 12 + payload_len + 4) {
        result.is_ok = false;
        result.error = PayloadLengthMismatch;
        return result;
    }
    
    uint8_t* payload_data = malloc(payload_len);
    if (!payload_data && payload_len > 0) {
        result.is_ok = false;
        result.error = BufferOverflow;
        return result;
    }
    
    if (payload_len > 0) {
        memcpy(payload_data, &raw->data[12], payload_len);
    }
    
    bytes* payload = malloc(sizeof(bytes));
    if (!payload) {
        free(payload_data);
        result.is_ok = false;
        result.error = BufferOverflow;
        return result;
    }
    
    payload->data = payload_data;
    payload->len = payload_len;
    
    uint32_t payload_checksum = read_be32(&raw->data[12 + payload_len]);
    uint32_t calculated_payload_checksum = calculate_checksum(payload_data, payload_len);
    
    if (calculated_payload_checksum != payload_checksum) {
        free(payload_data);
        free(payload);
        result.is_ok = false;
        result.error = ChecksumMismatch;
        return result;
    }
    
    result.is_ok = true;
    result.value.header_version = version;
    result.value.header_flags = flags;
    result.value.header_reserved = reserved;
    result.value.payload_len = payload_len;
    result.value.header_checksum = header_checksum;
    result.value.payload = payload;
    result.value.payload_checksum = payload_checksum;
    
    return result;
}

void free_packet(Packet* pkt) {
    if (pkt && pkt->payload) {
        free((void*)pkt->payload->data);
        free((void*)pkt->payload);
        memset(pkt, 0, sizeof(Packet));
    }
}

int main() {
    uint8_t test_data[] = {
        0x01,                           /* version */
        0x80,                           /* flags */
        0x00, 0x00,                     /* reserved */
        0x00, 0x00, 0x00, 0x05,        /* payload_len = 5 */
        0x00, 0x00, 0x00, 0x86,        /* header checksum = 1+128+0+0+0+0+0+5 = 134 */
        'H', 'e', 'l', 'l', 'o',       /* payload */
        0x00, 0x00, 0x01, 0xF4         /* payload checksum = 72+101+108+108+111 = 500 */
    };
    
    bytes raw = { test_data, sizeof(test_data) };
    
    printf("Testing parse_packet with valid data:\n");
    Result result = parse_packet(&raw, sizeof(test_data));
    if (result.is_ok) {
        printf("parse_packet() = SUCCESS (version=%d, flags=%d, payload_len=%u)\n", 
               result.value.header_version, result.value.header_flags, result.value.payload_len);
        free_packet(&result.value);
        printf("free_packet() = SUCCESS\n");
    } else {
        printf("parse_packet() = ERROR %d\n", result.error);
    }
    
    printf("Testing parse_packet with too short data:\n");
    bytes short_raw = { test_data, 5 };
    result = parse_packet(&short_raw, 5);
    printf("parse_packet() = ERROR %d\n", result.error);
    
    printf("Testing parse_packet with invalid version:\n");
    uint8_t invalid_version_data[] = {0x03, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x83, 0x00, 0x00, 0x00, 0x00};
    bytes invalid_raw = { invalid_version_data, sizeof(invalid_version_data) };
    result = parse_packet(&invalid_raw, sizeof(invalid_version_data));
    printf("parse_packet() = ERROR %d\n", result.error);
    
    return 0;
}