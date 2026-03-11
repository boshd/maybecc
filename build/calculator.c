#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

int32_t add(int32_t a, int32_t b) {
    return a + b;
}

int32_t subtract(int32_t a, int32_t b) {
    return a - b;
}

int32_t multiply(int32_t a, int32_t b) {
    return a * b;
}

uint32_t factorial(uint32_t n) {
    if (n > 12) {
        return 0; // Precondition violation
    }
    
    uint32_t result = 1;
    for (uint32_t i = 1; i <= n; i++) {
        result *= i;
    }
    return result;
}

int main(void) {
    // Test add function
    printf("add(5, 3) = %d\n", add(5, 3));
    printf("add(-10, 7) = %d\n", add(-10, 7));
    printf("add(0, 0) = %d\n", add(0, 0));
    
    // Test subtract function
    printf("subtract(10, 4) = %d\n", subtract(10, 4));
    printf("subtract(3, 8) = %d\n", subtract(3, 8));
    printf("subtract(-5, -2) = %d\n", subtract(-5, -2));
    
    // Test multiply function
    printf("multiply(6, 7) = %d\n", multiply(6, 7));
    printf("multiply(-3, 4) = %d\n", multiply(-3, 4));
    printf("multiply(0, 100) = %d\n", multiply(0, 100));
    
    // Test factorial function
    printf("factorial(0) = %u\n", factorial(0));
    printf("factorial(1) = %u\n", factorial(1));
    printf("factorial(5) = %u\n", factorial(5));
    printf("factorial(10) = %u\n", factorial(10));
    printf("factorial(12) = %u\n", factorial(12));
    
    return 0;
}