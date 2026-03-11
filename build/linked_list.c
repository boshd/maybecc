#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>

typedef struct ListNode {
    struct ListNode* prev;
    struct ListNode* next;
} ListNode;

typedef struct ListHead {
    ListNode sentinel;
} ListHead;

void list_init(ListHead* head) {
    head->sentinel.next = &head->sentinel;
    head->sentinel.prev = &head->sentinel;
}

bool list_is_empty(const ListHead* head) {
    return head->sentinel.next == &head->sentinel;
}

void list_push_front(ListHead* head, ListNode* node) {
    if (node == NULL) return;
    
    ListNode* old_first = head->sentinel.next;
    
    node->next = old_first;
    node->prev = &head->sentinel;
    old_first->prev = node;
    head->sentinel.next = node;
}

void list_push_back(ListHead* head, ListNode* node) {
    if (node == NULL) return;
    
    ListNode* old_last = head->sentinel.prev;
    
    node->prev = old_last;
    node->next = &head->sentinel;
    old_last->next = node;
    head->sentinel.prev = node;
}

void list_remove(ListNode* node) {
    if (node == NULL || node->prev == NULL || node->next == NULL) return;
    
    node->prev->next = node->next;
    node->next->prev = node->prev;
    node->next = NULL;
    node->prev = NULL;
}

ListNode* list_pop_front(ListHead* head) {
    if (list_is_empty(head)) return NULL;
    
    ListNode* node = head->sentinel.next;
    list_remove(node);
    return node;
}

int main() {
    ListHead head;
    ListNode node1, node2, node3;
    
    // Test list_init
    list_init(&head);
    printf("list_init(&head) = void\n");
    
    // Test list_is_empty on empty list
    bool empty = list_is_empty(&head);
    printf("list_is_empty(&head) = %s\n", empty ? "true" : "false");
    
    // Test list_push_front
    list_push_front(&head, &node1);
    printf("list_push_front(&head, &node1) = void\n");
    
    // Test list_is_empty on non-empty list
    empty = list_is_empty(&head);
    printf("list_is_empty(&head) = %s\n", empty ? "true" : "false");
    
    // Test list_push_back
    list_push_back(&head, &node2);
    printf("list_push_back(&head, &node2) = void\n");
    
    // Test another list_push_front
    list_push_front(&head, &node3);
    printf("list_push_front(&head, &node3) = void\n");
    
    // Test list_pop_front
    ListNode* popped = list_pop_front(&head);
    printf("list_pop_front(&head) = %p\n", (void*)popped);
    
    // Test another list_pop_front
    popped = list_pop_front(&head);
    printf("list_pop_front(&head) = %p\n", (void*)popped);
    
    // Test list_remove
    list_remove(&node2);
    printf("list_remove(&node2) = void\n");
    
    // Test list_is_empty after removing all
    empty = list_is_empty(&head);
    printf("list_is_empty(&head) = %s\n", empty ? "true" : "false");
    
    // Test list_pop_front on empty list
    popped = list_pop_front(&head);
    printf("list_pop_front(&head) = %p\n", (void*)popped);
    
    return 0;
}