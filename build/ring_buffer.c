#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

typedef struct {
    uint8_t* data;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
} RingBuffer;

typedef struct {
    bool some;
    RingBuffer value;
} OptionalRingBuffer;

typedef struct {
    bool some;
    uint8_t value;
} OptionalUint8;

OptionalRingBuffer ring_buffer_create(size_t capacity) {
    OptionalRingBuffer result = {false, {0}};
    
    if (capacity == 0 || capacity > 1048576) {
        return result;
    }
    
    uint8_t* data = malloc(capacity * sizeof(uint8_t));
    if (data == NULL) {
        return result;
    }
    
    result.some = true;
    result.value.data = data;
    result.value.capacity = capacity;
    result.value.head = 0;
    result.value.tail = 0;
    result.value.count = 0;
    
    return result;
}

bool ring_buffer_push(RingBuffer* buf, uint8_t byte) {
    if (buf == NULL) {
        return false;
    }
    
    if (buf->count == buf->capacity) {
        return false;
    }
    
    buf->data[buf->tail] = byte;
    buf->tail = (buf->tail + 1) % buf->capacity;
    buf->count++;
    
    return true;
}

OptionalUint8 ring_buffer_pop(RingBuffer* buf) {
    OptionalUint8 result = {false, 0};
    
    if (buf == NULL) {
        return result;
    }
    
    if (buf->count == 0) {
        return result;
    }
    
    result.some = true;
    result.value = buf->data[buf->head];
    buf->head = (buf->head + 1) % buf->capacity;
    buf->count--;
    
    return result;
}

void ring_buffer_destroy(RingBuffer* buf) {
    if (buf == NULL) {
        return;
    }
    
    free(buf->data);
    buf->data = NULL;
    buf->capacity = 0;
    buf->head = 0;
    buf->tail = 0;
    buf->count = 0;
}

int main() {
    // Test ring_buffer_create
    OptionalRingBuffer buf_opt = ring_buffer_create(5);
    printf("ring_buffer_create(5) = %s\n", buf_opt.some ? "Some" : "None");
    
    if (!buf_opt.some) {
        return 1;
    }
    
    RingBuffer buf = buf_opt.value;
    printf("buffer capacity = %zu, count = %zu\n", buf.capacity, buf.count);
    
    // Test ring_buffer_push
    bool push_result = ring_buffer_push(&buf, 42);
    printf("ring_buffer_push(&buf, 42) = %s\n", push_result ? "true" : "false");
    
    push_result = ring_buffer_push(&buf, 100);
    printf("ring_buffer_push(&buf, 100) = %s\n", push_result ? "true" : "false");
    
    push_result = ring_buffer_push(&buf, 200);
    printf("ring_buffer_push(&buf, 200) = %s\n", push_result ? "true" : "false");
    
    printf("buffer count after pushes = %zu\n", buf.count);
    
    // Test ring_buffer_pop
    OptionalUint8 pop_result = ring_buffer_pop(&buf);
    printf("ring_buffer_pop(&buf) = %s", pop_result.some ? "Some(" : "None");
    if (pop_result.some) {
        printf("%u)", pop_result.value);
    }
    printf("\n");
    
    pop_result = ring_buffer_pop(&buf);
    printf("ring_buffer_pop(&buf) = %s", pop_result.some ? "Some(" : "None");
    if (pop_result.some) {
        printf("%u)", pop_result.value);
    }
    printf("\n");
    
    printf("buffer count after pops = %zu\n", buf.count);
    
    // Test buffer full condition
    ring_buffer_push(&buf, 1);
    ring_buffer_push(&buf, 2);
    ring_buffer_push(&buf, 3);
    ring_buffer_push(&buf, 4);
    printf("buffer count when full = %zu\n", buf.count);
    
    bool full_push = ring_buffer_push(&buf, 5);
    printf("ring_buffer_push when full = %s\n", full_push ? "true" : "false");
    
    // Test empty condition
    for (int i = 0; i < 5; i++) {
        ring_buffer_pop(&buf);
    }
    printf("buffer count when empty = %zu\n", buf.count);
    
    OptionalUint8 empty_pop = ring_buffer_pop(&buf);
    printf("ring_buffer_pop when empty = %s\n", empty_pop.some ? "Some" : "None");
    
    // Test ring_buffer_destroy
    ring_buffer_destroy(&buf);
    printf("ring_buffer_destroy(&buf) = completed\n");
    
    return 0;
}