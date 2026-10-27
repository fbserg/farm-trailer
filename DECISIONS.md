# Safety decisions

## Preserve existing room assignments (October 26, 2026)

Decision: scope the parent vehicle registry to a trailer's persisted type during
synchronous menu creation and entry. Restore every original script table on return
or failure, including nested calls. Keep every old and accidental farm assignment.

Evidence: the current parent chooses a script type before its saved vehicle type,
allocates a room before preEnter, and retains the old type in the player record.
A preEnter cancellation is too late to prevent the wrong allocation. Menu capacity
checks also use the script type, so entry-only interception is insufficient.

Reopen if the parent honors persisted types directly or makes these calls asynchronous.

## Keep fail-closed farm exit interception

Decision: use postEnter to suppress free utilities. Keep a narrow exit wrapper and
recognize farm coordinates as well as the stored type. Remove only live zombies in
the parent's five-tile outside margin. Never remove corpses or livestock.

Evidence: RVHooks.emit catches callback errors and continues. An exit-hook error
would therefore fall through to the parent's corpse deletion. Its cleanup never
needed to remove live livestock. SP recovery must run before the wrapper decides.

Reopen if the parent supplies a reliable cleanup policy hook with fail-closed errors.

## Keep animal handoff on the authority that completes pickup

Decision: complete native pickup before entry/exit, then release only at the bound
farm assignment. If crossing fails, retain the native carrier. Old carriers without
a destination ID remain available for native manual placement.

Evidence: client perform and server complete are separate events. A mutable radial
menu can point at another trailer. Native carriers persist animal identity and state.
Two native player objects exercise assignment isolation, not real network peers.

Reopen after a live two-client session or a change to native timed-action networking.

## Permanent original perimeter (October 26, 2026)

Decision: upgrade only original farm walls/fences in place, with dedicated stable
sprite IDs and a one-tile invisible collision border outside the farm. Block native
climbing, normal attacks, fire and sledge actions on tagged boundary objects.
Preserve player construction and skip conflicting squares. Missing walls remain
missing, but clear outer tiles receive the border. Never replace vanilla sprites.

Evidence: native startup clears the sprite manager after OnInitWorld. Register at
OnLoadedTileDefinitions before saved objects resolve IDs. Native creation/restart
checks block players, cattle and hens, fire and sledge actions. Portable checks
preserve existing objects and skip construction conflicts.

Reopen if the game changes sprite serialization or boundary collision behavior.
Admin tools and mods that bypass normal actions remain outside this protection.
