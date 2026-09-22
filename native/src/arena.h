/* arena.h - request-scoped memory arena.
 *
 * A request arena owns all temporary allocations for one HTTP request.
 * It is a simple bump allocator: allocations advance a cursor within a
 * chain of fixed-size blocks. When the current block fills, a new block is
 * allocated. At request end, arena_release() frees every block in one step.
 *
 * Ownership:
 *   - The arena owns every allocation made from it.
 *   - Borrowed pointers into the arena are valid only until arena_release().
 *   - arena_release() is called exactly once per request, on both the
 *     success and error paths.
 *
 * This is not a general-purpose allocator. It exists so request cleanup
 * does not depend on dozens of scattered manual frees.
 */

#ifndef CATBA_ARENA_H
#define CATBA_ARENA_H

#include <stddef.h>

/* Default block size for arena allocations. */
#define CB_ARENA_BLOCK_SIZE 8192

/* Alignment for arena allocations. */
#define CB_ARENA_ALIGN 16

/* The arena: a linked list of memory blocks. */
typedef struct cb_arena_block {
    struct cb_arena_block *next;  /* next block in chain (or NULL) */
    size_t used;                  /* bytes consumed in this block */
    size_t cap;                   /* capacity of this block */
    /* payload follows immediately after this struct */
} cb_arena_block;

typedef struct cb_arena {
    cb_arena_block *first;  /* first block (head of chain) */
    cb_arena_block *cur;    /* current block for allocations */
    size_t total_alloc;     /* total bytes allocated (for diagnostics) */
    int alloc_count;        /* number of alloc calls (for diagnostics) */
} cb_arena;

/* Create a new arena. Returns NULL on allocation failure. */
cb_arena *cb_arena_create(void);

/* Allocate `size` bytes from the arena. Returns NULL on failure.
 * Memory is zero-initialized. The arena owns the returned pointer. */
void *cb_arena_alloc(cb_arena *a, size_t size);

/* Allocate `count * size` bytes, with overflow check. Returns NULL on
 * overflow or allocation failure. Memory is zero-initialized. */
void *cb_arena_calloc(cb_arena *a, size_t count, size_t size);

/* Duplicate a string of length `len` into the arena. Returns NULL on
 * failure. The arena owns the returned pointer. */
char *cb_arena_dup(cb_arena *a, const char *src, size_t len);

/* Duplicate a NUL-terminated string into the arena. Returns NULL on
 * failure. The arena owns the returned pointer. */
char *cb_arena_dup_str(cb_arena *a, const char *src);

/* Release every block in the arena and the arena struct itself.
 * After this call, all pointers previously allocated from the arena are
 * invalid. Must be called exactly once. Safe to call with NULL (no-op). */
void cb_arena_release(cb_arena *a);

/* Return total bytes allocated from the arena (diagnostics only). */
size_t cb_arena_total(const cb_arena *a);

/* Return number of allocations made (diagnostics only). */
int cb_arena_count(const cb_arena *a);

#endif /* CATBA_ARENA_H */
