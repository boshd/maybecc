#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    uint8_t* buf;
    size_t capacity;
    size_t bit_pos;
} BitStream;

typedef struct {
    bool has_value;
    uint32_t value;
} Optional_uint32_t;

BitStream bs_create(uint8_t* buf, size_t capacity) {
    BitStream stream;
    stream.buf = buf;
    stream.capacity = capacity;
    stream.bit_pos = 0;
    return stream;
}

bool bs_write(BitStream* stream, uint32_t value, uint8_t bits) {
    if (bits < 1 || bits > 32) {
        return false;
    }
    
    size_t total_bits_needed = stream->bit_pos + bits;
    if (total_bits_needed > stream->capacity * 8) {
        return false;
    }
    
    for (int i = bits - 1; i >= 0; i--) {
        uint32_t bit = (value >> i) & 1;
        size_t byte_index = stream->bit_pos / 8;
        size_t bit_index = stream->bit_pos % 8;
        
        if (bit) {
            stream->buf[byte_index] |= (1 << (7 - bit_index));
        } else {
            stream->buf[byte_index] &= ~(1 << (7 - bit_index));
        }
        
        stream->bit_pos++;
    }
    
    return true;
}

Optional_uint32_t bs_read(BitStream* stream, uint8_t bits) {
    Optional_uint32_t result = {false, 0};
    
    if (bits < 1 || bits > 32) {
        return result;
    }
    
    if (stream->bit_pos + bits > stream->capacity * 8) {
        return result;
    }
    
    uint32_t value = 0;
    for (int i = 0; i < bits; i++) {
        size_t byte_index = stream->bit_pos / 8;
        size_t bit_index = stream->bit_pos % 8;
        
        uint32_t bit = (stream->buf[byte_index] >> (7 - bit_index)) & 1;
        value = (value << 1) | bit;
        
        stream->bit_pos++;
    }
    
    result.has_value = true;
    result.value = value;
    return result;
}

int main() {
    uint8_t buffer[4];
    memset(buffer, 0, sizeof(buffer));
    
    BitStream stream = bs_create(buffer, 4);
    printf("bs_create(buffer, 4) = {buf=%p, capacity=%zu, bit_pos=%zu}\n", 
           (void*)stream.buf, stream.capacity, stream.bit_pos);
    
    bool write_result1 = bs_write(&stream, 0xA5, 8);
    printf("bs_write(&stream, 0xA5, 8) = %s\n", write_result1 ? "true" : "false");
    
    bool write_result2 = bs_write(&stream, 0x3, 4);
    printf("bs_write(&stream, 0x3, 4) = %s\n", write_result2 ? "true" : "false");
    
    stream.bit_pos = 0;
    
    Optional_uint32_t read_result1 = bs_read(&stream, 8);
    if (read_result1.has_value) {
        printf("bs_read(&stream, 8) = 0x%X\n", read_result1.value);
    } else {
        printf("bs_read(&stream, 8) = None\n");
    }
    
    Optional_uint32_t read_result2 = bs_read(&stream, 4);
    if (read_result2.has_value) {
        printf("bs_read(&stream, 4) = 0x%X\n", read_result2.value);
    } else {
        printf("bs_read(&stream, 4) = None\n");
    }
    
    Optional_uint32_t read_result3 = bs_read(&stream, 25);
    if (read_result3.has_value) {
        printf("bs_read(&stream, 25) = 0x%X\n", read_result3.value);
    } else {
        printf("bs_read(&stream, 25) = None\n");
    }
    
    return 0;
}