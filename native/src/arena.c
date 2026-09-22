/* arena.c - request-scoped memory arena implementation.
 *
 * Bump allocator with block growth. All allocations from the arena are
 * owned by the arena and freed in one step by cb_arena_release().
 */

#include "arena.h"

#include <stdlib.h>
#include <string.h>

/* Allocate a new block of at least `need` bytes payload. */
static cb_arena_block *new_block(size_t need)
{
    size_t payload = CB_ARENA_BLOCK_SIZE;
    if (need > payload)
        payload = need;

    /* Check overflow: payload + sizeof(block) must not overflow. */
    if (payload > SIZE_MAX - sizeof(cb_arena_block))
        return NULL;

    size_t total = sizeof(cb_arena_block) + payload;
    cb_arena_block *blk = (cb_arena_block *)calloc(1, total);
    if (!blk)
        return NULL;

    blk->next = NULL;
    blk->used = 0;
    blk->cap = payload;
    return blk;
}

cb_arena *cb_arena_create(void)
{
    cb_arena *a = (cb_arena *)calloc(1, sizeof(*a));
    if (!a)
        return NULL;

    cb_arena_block *blk = new_block(0);
    if (!blk) {
        free(a);
        return NULL;
    }

    a->first = blk;
    a->cur = blk;
    a->total_alloc = 0;
    a->alloc_count = 0;
    return a;
}

/* Align a size up to CB_ARENA_ALIGN. */
static size_t align_up(size_t n)
{
    return (n + (CB_ARENA_ALIGN - 1)) & ~((size_t)(CB_ARENA_ALIGN - 1));
}

void *cb_arena_alloc(cb_arena *a, size_t size)
{
    if (!a || size == 0)
        return NULL;

    /* Guard against SIZE_MAX overflow in align_up. */
    if (size > SIZE_MAX - (CB_ARENA_ALIGN - 1))
        return NULL;

    size_t need = align_up(size);

    /* If the current block cannot fit, allocate a new one. */
    if (a->cur->used + need > a->cur->cap) {
        cb_arena_block *blk = new_block(need);
        if (!blk)
            return NULL;
        /* Append the new block to the chain. */
        blk->next = a->cur->next;
        a->cur->next = blk;
        a->cur = blk;
    }

    /* Bump-allocate from the current block. */
    /* Payload starts right after the block header. */
    char *payload = (char *)(a->cur + 1);
    void *result = payload + a->cur->used;
    a->cur->used += need;
    a->total_alloc += need;
    a->alloc_count++;

    /* Zero-initialize (calloc semantics for safety). */
    memset(result, 0, size);
    return result;
}

void *cb_arena_calloc(cb_arena *a, size_t count, size_t size)
{
    if (!a || count == 0 || size == 0)
        return NULL;

    /* Overflow check: count * size must not overflow. */
    if (count > SIZE_MAX / size)
        return NULL;

    return cb_arena_alloc(a, count * size);
}

char *cb_arena_dup(cb_arena *a, const char *src, size_t len)
{
    if (!a || !src)
        return NULL;

    /* Need len + 1 for the NUL terminator. Check overflow. */
    if (len > SIZE_MAX - 1)
        return NULL;

    char *dst = (char *)cb_arena_alloc(a, len + 1);
    if (!dst)
        return NULL;
    memcpy(dst, src, len);
    dst[len] = '\0';
    return dst;
}

char *cb_arena_dup_str(cb_arena *a, const char *src)
{
    if (!a || !src)
        return NULL;
    return cb_arena_dup(a, src, strlen(src));
}

void cb_arena_release(cb_arena *a)
{
    if (!a)
        return;

    /* Free every block in the chain. */
    cb_arena_block *blk = a->first;
    while (blk) {
        cb_arena_block *next = blk->next;
        free(blk);
        blk = next;
    }

    /* Free the arena struct. */
    free(a);
}

size_t cb_arena_total(const cb_arena *a)
{
    return a ? a->total_alloc : 0;
}

int cb_arena_count(const cb_arena *a)
{
    return a ? a->alloc_count : 0;
}
