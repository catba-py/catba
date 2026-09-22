/* arena.h - request-scoped memory arena.
 *
 * Not yet implemented. Declared here so other modules can reference it.
 * Implementation arrives in the next commit.
 */

#ifndef CATBA_ARENA_H
#define CATBA_ARENA_H

#include <stddef.h>

/* A request arena owns all temporary allocations for one request.
 * Released in one step at request end. */
typedef struct cb_arena cb_arena;

#endif /* CATBA_ARENA_H */
