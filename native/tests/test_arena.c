/* test_arena.c - verify the request arena allocates and releases correctly. */

#include "arena.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

static void test_basic_alloc(void)
{
    cb_arena *a = cb_arena_create();
    assert(a != NULL);

    void *p = cb_arena_alloc(a, 100);
    assert(p != NULL);
    assert(cb_arena_count(a) == 1);
    assert(cb_arena_total(a) >= 100);

    /* Memory should be zero-initialized. */
    char *cp = (char *)p;
    for (int i = 0; i < 100; i++)
        assert(cp[i] == 0);

    cb_arena_release(a);
    printf("  basic alloc: ok\n");
}

static void test_multiple_allocs(void)
{
    cb_arena *a = cb_arena_create();
    assert(a != NULL);

    for (int i = 0; i < 100; i++) {
        void *p = cb_arena_alloc(a, 64);
        assert(p != NULL);
    }
    assert(cb_arena_count(a) == 100);

    cb_arena_release(a);
    printf("  multiple allocs: ok\n");
}

static void test_block_growth(void)
{
    cb_arena *a = cb_arena_create();
    assert(a != NULL);

    /* Allocate more than one block to trigger growth. */
    void *p1 = cb_arena_alloc(a, CB_ARENA_BLOCK_SIZE);
    assert(p1 != NULL);

    void *p2 = cb_arena_alloc(a, CB_ARENA_BLOCK_SIZE);
    assert(p2 != NULL);

    /* p1 and p2 should be in different blocks. */
    assert(p1 != p2);

    cb_arena_release(a);
    printf("  block growth: ok\n");
}

static void test_string_dup(void)
{
    cb_arena *a = cb_arena_create();
    assert(a != NULL);

    char *s = cb_arena_dup_str(a, "hello world");
    assert(s != NULL);
    assert(strcmp(s, "hello world") == 0);

    char *s2 = cb_arena_dup(a, "partial", 4);
    assert(s2 != NULL);
    assert(strcmp(s2, "part") == 0);

    cb_arena_release(a);
    printf("  string dup: ok\n");
}

static void test_calloc_overflow(void)
{
    cb_arena *a = cb_arena_create();
    assert(a != NULL);

    /* Overflow: SIZE_MAX / 2 * 3 should overflow. */
    void *p = cb_arena_calloc(a, SIZE_MAX / 2, 3);
    assert(p == NULL);

    /* Normal calloc works. */
    p = cb_arena_calloc(a, 10, 8);
    assert(p != NULL);

    cb_arena_release(a);
    printf("  calloc overflow: ok\n");
}

static void test_release_null_safe(void)
{
    cb_arena_release(NULL);  /* must not crash */
    printf("  release NULL: ok\n");
}

static void test_large_alloc(void)
{
    cb_arena *a = cb_arena_create();
    assert(a != NULL);

    /* Allocate something larger than the default block. */
    void *p = cb_arena_alloc(a, CB_ARENA_BLOCK_SIZE * 4);
    assert(p != NULL);

    cb_arena_release(a);
    printf("  large alloc: ok\n");
}

int main(void)
{
    printf("test_arena:\n");
    test_basic_alloc();
    test_multiple_allocs();
    test_block_growth();
    test_string_dup();
    test_calloc_overflow();
    test_release_null_safe();
    test_large_alloc();
    printf("ALL ARENA TESTS PASSED\n");
    return 0;
}
