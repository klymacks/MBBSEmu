MegaMMUD v2.1 (08/08/2026)  
---------------------------------------------------------------------------  
[COMBAT & SPELLCASTING]  
- NEW: Profiles for combat, spells, and health settings + remote w/[at]profile #  
- NEW: Party option: Rest Healing Applies to Party (party heals while resting)  
- UP: Unless stealthed or full, party leader now rests while waiting on party  
- UP: Cure poison will now occur before healing when out of combat  
- UP: Spell level and mana fields widened to 3 digits (mana 999, level 255)  
- FIX: Not self-healing while resting with 'heal party over self' turned on  

[COMBAT FLOW, ATTACKS, AND STABILITY]  
- NEW: Party option: Attack late - works in combo. with someone attacking last  
- FIX: Repeating party status (par) checks after a combat round  
- FIX: Glancing blows now count as a swing for round timing  
- FIX: Extraneous [Bueller?] messages when in all off / manually playing  
- FIX: Weapon immunity flagging made more robust through attack confirmations  
- FIX: Attack last not reacting to party member area-attacks spells  
- FIX: Client could lag showing Inventory, Who, or Top during combat  

[NAVIGATION, EVENTS, AND QUALITY OF LIFE]  
- NEW: Plugin support for extending client functionality  
- NEW: Talk option: [at]where replies with map/room info via 'room' command  
- NEW: Remote command [at]auto-hangup [on|off] to allow/block hangups  
- UP: [at]path/[at]status now reports destination and remaining steps  
- FIX: Picking the room you're in from the right-click list moved or looped  
- FIX: Chained Ability Monitors never checked with short trigger timers  
- FIX: Ability Monitor stopped checking for the rest of the session after a death  
- FIX: Ability Monitors on the same timer would only check the first two  
- FIX: Ability Monitor status now reported in [at]settings  
- FIX: [at]goto/[at]loop after [at]stop replying {ok} but never moving  
- FIX: Remote commands and their ON/OFF actions are no longer case sensitive  
- FIX: Saving game data no longer makes an active path/loop lose its place  
- FIX: Error messages no longer pause the game or automation while displayed  
- FIX: Steps remaining showing "?" after a new destination mid-path or loop  
- FIX: Steps remaining counted down instead of up when backtracking a path  
- FIX: Toggling auto-modes mid-move causing extra steps and a lost path  
- FIX: PATHS/Paramud: Added rope requirement to SLLAM7WS (Underground River)  
- FIX: PATHS/Paramud: Removed SSTBRSMN, STMDRHRS, STMDRSMN (tunnels to Rhudar)  

[PARSER, ITEM, AND FILE HANDLING]  
- NEW: Loot option: Auto-recover your own corpses (GreaterMUD)  
- NEW: Loot option: Collect only while engaged in combat  
- UP: Share party cash will now default to OFF  
- UP: Added metadata and hardened DLL loading to try and fend off malware flags  
- UP: Executable now digitally signed to try and fend off malware flags  
- FIX: Corpses are no longer added to the known items database (GreaterMUD)  
- FIX: 0-quantity buy/sell/get/give no longer adds bogus items or counts  
- FIX: Game data loading issues after copying/moving character files  
- FIX: Possible crash after editing game data while at a shop or bank  
- FIX: Endlessly retrying to get an item another player already took  
- FIX: Small delay after "You don't see..." messages  
- FIX: Mob names will no longer substring match: shadow won't match shadowraith  

[INTERFACE AND WORDING UPDATES]  
- NEW: Backscroll window now shows history in full ANSI color and font  
- UP: The Cash settings tab is now called Loot  
- UP: Time window now shows each line item's percentage of the total  
- UP: Exp. graph can show 1hr/30min/15min/5min rolling trend lines  
- UP: Telepaths, pages, and directed messages you send now show in Conversations  
- UP: Dark mode moved to global setting-- char ini setting should migrate over  
- FIX: Dark mode: options staying dimmed after becoming available again  


MegaMMUD v2.0.5 (07/17/2026)  
---------------------------------------------------------------------------  
- NEW: Dark mode added (see display settings, requires save+restart)  
- NEW: Ability Monitor (see Events tab) periodically check "abil #" values  
- UP: Conversations window history size now configurable (default 200, max 5000)  
- UP: Conversations window rebuilds much faster after changing view filters  
- UP: Back-scroll buffer updated with default 1M bytes (~1MB) and max 5M bytes  
- UP: Added a show password button to the BBS tab  
- UP: Added a time axis + time info on hover to the exp. rate graph  
- UP: Added support for "You hurl your [weapon]" hit/miss messages  
- UP: Bless during combat will now default to ON  
- UP: Confirm hangup, polite attacks, and auto-train will now default to OFF  
- UP: Light dimly lit rooms and pop-up afk messages will now default to OFF  
- UP: Saving gamedata will no longer trigger a 'who' unless players were modified  
- FIX: Conversations window could stop updating after changing filters while full  
- FIX: Conversations window jumping to the newest line even while paused  
- FIX: Not healing while resting  
- FIX: Party healing ignoring the minor heal mana % requirement in combat  
- FIX: Recasting blesses by seconds retrying once instead of until successful  
- FIX: [at]auto-search on/off remote command being rejected as invalid  
- FIX: Stock titles updated, GreaterMUD titles added for level estimation  
- FIX: Auto-train not recognizing train success/failure msgs on GreaterMUD  
- FIX: Auto-train bouncing in/out of the trainer room waiting for full HPs  
- FIX: Re-attack loop on non-hostile mobs when attack non-hostiles enabled  
- FIX: "Run if BS fails" running away even when the backstab landed  
- FIX: Full stash rooms re-sending stash instead of moving to the next room  
- FIX: Paste now checks once a second for valid clipboard data  
- FIX: Stale/corrupt player records causing crashes or not aging out  
- FIX: Warning on save if a auto-deposit is enabled but chosen bank is unknown  
- FIX: Auto-deposit Bank of Godfrey will auto-correct to "Bank of Godfrey-1 297"  
- FIX: Aborted path recordings breaking all movement (incl. low-HP run-away)  
- FIX: Unloadable current path now dropped/re-armed instead of erroring forever  
- FIX: Renaming/saving a new ROOMLOO#.mp and the existing ROOMLOOP.mp is deleted  
- FIX: Repeatedly retrying hide in rooms while traveling a path  
- FIX: DATA/Paramud: Kang race experience chart %  
- FIX: DATA/Paramud: Keypad enter key macro mapping  
- FIX: PATHS/Paramud: Fixed KHAZKARM (again... room destination was missing...)  


MegaMMUD v2.0.4 (07/09/2026)  
---------------------------------------------------------------------------  
- UP/FIX: Gamedata saving reworked to address data issues with multiple instances  
- UP: Old "Don't attack here" path step flag deprecated (but remains functional)  
- UP: New "Don't attack here" flag added that functions more intuitively (see help)  
- FIX: Crash tracking newly added/discovered players  
- FIX: Showing abbreviated experience needed (##.## M) when not over level  
- FIX(again): Running too many rooms when running  


MegaMMUD v2.0.3 (No more Beta) (06/21/2026)  
---------------------------------------------------------------------------  
- UP: Time to level will now show time beyond current level (+on/off option)  
- UP: Expanded player options for no heal, no bless, and no cure  
- UP: Attack immunity flags should only be applied after target confirmation  
- UP: Option in display settings to bring back the clock on the status bar  
- UP: Added a Copy button on the BBS tab - the New button will use defaults  
- FIX: Experience calculation for stock boards above level 55  
- FIX: Accurate experience and CP calc for Paramud (current and next patch)  
- FIX: Inaccurate "no spell msg seen after multiple rounds" messages  
- FIX: More fixes to unintentional [reset] messages after repeated commands  
- FIX: Crash after consecutive command resets in certain scenarios  
- FIX: Removing weapons causing a loop of your command had no effect  
- FIX: Target tracking with guard mobs ("moves to protect")  
- FIX: Immunity flags not being applied to guard mobs  
- FIX: Not applying weapon immunity flags when bogus weapon defined  
- FIX: Not activating paste after cut/copy text from talk window input box  
- FIX: Not detecting disconnection during the connection process in some cases  
- FIX: Some area spells without defined messages considered as incoming dmg  
- FIX: Functionality hard coded for Mystics now function w/other Kai classes  
- FIX: Queued spell message responses losing friendly target w/combat target  
- FIX: Proper combat spell re-engagement in some edge cases  
- FIX: Not re-enabling auto-combat in some situations  
- FIX: Trying to re-attack monsters no longer in the room after re-connecting  
- FIX: Slamming in to walls when we can't see not entering in to lost mode  
- FIX: Running more rooms than configured for low HP at the end of a path  
- FIX: Not moving after hiding from being prone once the effect wears off  
- FIX: Casting blesses with monsters in the room and breaking sneak  
- FIX: Few instances where having no path would cause it to stop doing things  
- FIX: Time analysis not switching from combat to mana regen when meditating  
- FIX: @ok will now clear all status effects from the party member  
- PATHS/Paramud: Fixed KHAZKARM (room code was incorrect)  
- PATHS/Paramud: Fixed GSMNFCCO (missing a down exit at the end)  


MegaMMUD v2.0 Beta - Patch 1 (05/28/2026)  
---------------------------------------------------------------------------  
- NEW: Option on Other tab to auto-cast spells towards the end of the round  
- NEW: Option on Other tab to prioritize cures over minor heals (see help)  
- UP: par output now clears internal poison flags when no longer indicated  
- UP: Increased number of session immunity flags for mobs from 32 to 500  
- UP: Identical pre-rest/med cmds won't retrigger in transition of rest<>med  
- UP: pre-rest/med will now trigger if the opposite pre-rest/med is disabled  
- UP: pre/post-meditate will now default to disabled for better migration  
- UP: Added a once-per-session warning for the min monsters setting  
- UP: Added support for detecting "x y z into the room!" messages  
- UP: Increased max ANSI rows to 200 (max columns remains 132)  
- UP: Priority text on buffs tab will turn red when global priority enabled  
- FIX: Not applying manual/forced hp regen / mana regen spells in some cases  
- FIX: Extra re-attacks when attacking last in some instances  
- FIX: Coin weight calculation for GreaterMUD (total coins vs each coin)  
- FIX: Typing "help statcommand" in GreaterMUD throwing off the client  
- FIX: Providing light in rooms you couldn't see in was all messed up  
- FIX: Not attacking mobs when you can't see in some cases  
- FIX: Special commands (go hole, etc) when moving through dark rooms  
- FIX: Self heal out of combat ignoring configured health/mana percentages  
- FIX: Area party heal requiring an alternative minor/major healing target  
- FIX: Unintentional [reset] messages after repeated commands  
- FIX: Spam-re-attacks mid-combat after bless/heals  
- FIX: Capture more standard-format "You x the y for z damage" messages  
- FIX: Moving in response to remote commands when below hangup thresholds  


MegaMMUD v2.0 Beta (05/17/2026)  
---------------------------------------------------------------------------  
[COMBAT & SPELLCASTING]  
- NEW: Round timer in status bar with automatic tracking  
- NEW: Redesigned spell combat with additional attacks and better tracking  
- Added option to prefer melee attacks over configured spell attacks  
- Added self minor heal and completely re-worked healing & curing priorities  
- Offensive spells can now be assigned to a heal slot  
- Weapons and combat spells will remember temporary immunity versus mobs  
- Added party area/room-heal spell options  
- Added a party option to always heal the lowest member (including yourself)  
- Added a 'Send PAR after combat round' option for faster HP updates  
- Added option to prioritize applying blesses over casting heals (other tab)  
- Added option to recast bless spells based on time (preemptive casting)  
- Added tracking for pasted and manually typed commands and attacks  
- Added support for multiple commands in a spell's Special Command box  
- If the target is immune to backstab, another target will be attempted  
- Added pre/post backstab and meditate commands, 255 character limit  
- Pre/Post rest and custom commands now allow up to 255 characters  
- Added checkboxes to enable/disable pre/post commands boxes  
- Fixed class spell magery type and level for new and modified classes  
- Added support for bard-2 and bard-3 class and spell distinctions  
- Improved mana regen tracking and faster flux recasts  
- Spells with 0 mana cost won't assume to have used your per-round spell lock  
- When an area spell finishes a mob, the client now sends break [stock only]  
* NOTE Longer 255-char input boxes may affect rollback to older versions  
* Special thanks to R1dic for help in stress-testing things  

[COMBAT FLOW, ATTACKS, AND STABILITY]  
- Added @auto-pre to toggle multi-pre and pre-attacks remotely  
- Added dedicated pre-multi and multi-attack stats to the statistics window  
- Added a stats-window toggle to show or hide physical and spell attacks  
- Added fail-safes to detect lapses in outbound combat  
- Added a minimum monsters field - only used when pathing w/auto-nuke enabled  
- Min/Max/Exp monster limits will always run 1 room forward on path  
- Added new monster flag: "Stop to kill if able" (see help for description)  
- Added some other multi-cast-related options (see help on combat settings)  
- Added a minimum monsters field - only used when pathing w/auto-nuke enabled  
- Attacks other than a[ttack] now re-engage after a landed or missed backstab  
- Stopped sending break before combat while sneaking, except when punching  
- After rest/med, now won't rest/med again until dipping below thresholds  
- Added a 10-attempt limit for consecutive sneak or hide retries  
- @wait and @ok now resend after failed actions such as confusion  
- @goto now clears the current loop to stop characters from running off  
- Added character load check to verify that assigned spells are available  
- Fix for not reacting to some attack messages  

[NAVIGATION, EVENTS, AND QUALITY OF LIFE]  
- Stock, Paramud, and Mudrev default gamedata updated with latest information  
- Most default paths/loops updated to include map/room numbers in their name  
- Enlarged the How to Get There window and made it resizable  
- Added total steps and requirements to the top of the How to Get There window  
- Added a new option to pause events during combat  
- Added keyboard shortcuts for deposit-all, get-all, and equip-all (Ctrl+D/G/E)  
- Added menu shortcuts for combat, events, and party (Alt+M/V/P)  
- Added an event hotkey and @auto-event remote command (Alt+E)  
- Added a Back Track hotkey to go back one step (Alt+A)  
- Added a Go Anyway option to override level restrictions on paths  
- Improved speed at which rooms re-learn, when enabled  
- Improved path selection around avoids and level restrictions  
- Added support for l[ook] [direction] path steps  
- Added "hidden" OG Mega Live Map w/minimally improved functionality  

[PARSER, ITEM, AND FILE HANDLING]  
- Added support for "You are already wearing" equip messages  
- Added support for item quantity messages in GreaterMUD pickup/drop/sell/buy  
- Message auto-responses that cast spells will now wait to cast until ready  
- New items auto-added from inventory will no longer auto-collect and equip  
- Item worn slot will now be auto-learned from inventory output when equipped  
- Improved parsing of large room item quantities, mainly in GreaterMUD  
- Monsters automatically added will have common descriptive adjectives removed  
- New mobs will start as unknown and avoided, but will attack once provoked  
- Messages are now scanned at startup for conflicts with game parsing routines  
- Added a data-directory browse button on the General tab  
- Character saves are now blocked outside of [DATADIR]\Chars  
- Fixed saving character files when the path contains a period  
- Fixed errors saving players.md for new characters  
- Fixed missing .cap extensions on capture files  

[INTERFACE AND WORDING UPDATES]  
- Removed Rng and Avg prefixes on player stats to allow larger numbers  
- Updated wording for the @auto-all on and off response  
- Updated window titles to include character name, class, and BBS name  
- Updated toolbar icons to higher quality graphics  
- Updated default toolbar options and fixed check boxes on the edit screen  
- Escape can now cancel or close many windows that would not close previously  
- New option to reset window positions (edit menu)  
- Added buttons to quickly populate weapons / shield on the combat tab  
- Added Reset Internals to the Edit menu; it performs the same action as @reset  
- Added "Show Item Weights" to Edit menu; prints current inventory w/weight  
- Added weight of items to inventory calculator  
- Added option to show the party window while solo (display tab)  
- Re-ordered tab strip in settings close to pre-2.0 layout by popular request  
- Added filter buttons to most of the tabs on the game data screen  
- Exposed "Fix" button on monster game data to scan for potential issues  
- Fixed gamedata issue where the lower # of same-named records would be deleted  
- Default (stock) gamedata updated with some duplicate spells cleaned up  
- Reduced Telnet and WSOCK32 message spam  
- Attempted to reduce delays during connect and disconnect sequences  
- Ctrl+Alt+D now toggles a debug mode to help track and report issues  

[BUG FIXES]  
- Fix from 2.0 Alpha regarding delays after item swaps and mass-equip messages  
- Fixed issues with Windows UAC and folder permissions out of the (x86) folder  
- Fixed area-spell damage credit when hits land between mobs while partying  
- Fixed items being calculated with negative weight (also see new menu item)  
- Fixed premature party healing after rejoining, before health is known  
- Fixed not sending par when in a party with combat turned off  
- Fixed attack verbs: rakes, rams, snaps, spins, tramples, whacks  
- Fixed backstabs counting as misses when extra weapon damage is dealt  
- Fixed combat not auto-engaging after stopping before a boss room  
- Fixed bless spells in slots 6-10 not resetting after a stat output  
- Fixed spell attacks continuing when mana drops below required spell mana  
- Fixed multiple movement commands being sent without waiting in some cases  
- Fixed stash points being ignored in the first room of a path  
- Fixed missed inventory checks when monsters are in the room  
- Fixed issue with paths changes altering default when you choose char or all  
- Fixed pathing error messages pausing all client activity until cleared  
- Fixed malformed player names being added + false-positive PVP engagements  
- Fix for never showing "a anything" text in the conversation window  
- Possible fix for occasional allow-paste block (open settings to fix)  
- Fixed save of window positions on multi-monitor setups  
- If auto-loading the last INI fails, auto-load is now turned off  


MegaMMUD v2.0 Alpha (02/23/2026)  
---------------------------------------------------------------------------  
- Registration removed  
- Added option to only stash coin up to a chosen coin type  
- Added support for eyes, face, worn, "everywhere", and second wrist slot  
- Added support for "[PARADIGM]:" realm entry prompt  
- Added support for detecting "None" (vs NONE!) exit type  
- Added search/filter box to Goto Location list  
- Can now press escape to cancel the goto list  
- Disabled conversation history mouse scrolling and auto-submit  
- Filename will now be shown before the app name in the titlebar/taskbar  
- Moved main megamud.ini to be next to megamud.exe (instead of c:\windows)  
- Added default BBS sign-on prompts and replys for fresh installs  
- Doubled the number of internal loops performed to find the best path  
- Back-scroll buffer limit increased to 1048576 bytes (from 32000)  
- Added Shift+F3 shortcut for 'find new' on back-scroll window  
- Expanded HP/MP on party windows to 5 digits  
- Fixed sizing of party window on some displays and operating systems  
- Increased exp calculation up to level 500  
- Added "millions per hour" experience notation (### m/hr)  
- Collected copper total now supports over 4.2B (limit UINT > ULL)  
- Better handling of pre/post cmds, message responses, etc that equip items  
- Fix for periods becoming part of player/monster names while exiting the realm  
- Fix for hiding and pausing at the first room one can hide after pathing somewhere  
- Fixed rollover of time on the time analysis window  
- Fixes for recursive receive/strcpy overloads/crashes **  
- Fix crash/halt when picking up coin near encumbrance limits **  
- Dial-up/Modem/ZModem functionality removed  
- Known Issue: Not compatible with Windows XP (may or may not fix)  

Please submit error reports and feature requests at https://www.mudinfo.net/viewforum.php?f=68

Thank you to Merlin for creating MegaMUD. Brought to you by Apathy and Syntax.