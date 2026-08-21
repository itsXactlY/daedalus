# Navigation Trap Fix — 2026-06-16

## Problem
Mimo's uncommitted changes removed `Graph` and `Timeline` from the bottom navigation bar (7 → 5 items) but Dashboard tiles (M03 "EDGES", M06 "PEERS", M11 "ENGINE") still navigated to those routes. This created navigation traps — users could enter the screens but had no BackHandler to exit.

## Symptoms
- User taps M03 "EDGES" tile on Dashboard
- GraphScreen opens (displays nodes/edges correctly)
- System back button does nothing (no BackHandler)
- Bottom nav bar has no Graph icon to return to
- User is "stuck" — must force-close or use recents

## Fix Applied
Added `BackHandler` to both trapped screens and wired `onBack` callbacks in NavGraph:

### GraphScreen.kt
```diff
+ import androidx.activity.compose.BackHandler

 @Composable
-fun GraphScreen(viewModel: MazemakerViewModel, onNavigateToMemory: (Int) -> Unit = {}) {
+ fun GraphScreen(
+     viewModel: MazemakerViewModel,
+     onNavigateToMemory: (Int) -> Unit = {},
+     onBack: () -> Unit = {}
+ ) {
+     BackHandler { onBack() }
```

### ThinkScreen.kt
```diff
+ import androidx.activity.compose.BackHandler

 @Composable
-fun ThinkScreen(viewModel: MazemakerViewModel, onNavigateToMemory: (Int) -> Unit = {}) {
+ fun ThinkScreen(
+     viewModel: MazemakerViewModel,
+     onNavigateToMemory: (Int) -> Unit = {},
+     onBack: () -> Unit = {}
+ ) {
+     BackHandler { onBack() }
```

### MazemakerNavGraph.kt
```diff
 composable(Screen.Graph.route) {
     GraphScreen(
         viewModel = viewModel,
         onNavigateToMemory = { id ->
             navController.navigate(Screen.MemoryDetail.createRoute(id))
         },
+        onBack = { navController.popBackStack() }
     )
 }

 composable(Screen.Think.route) {
     ThinkScreen(
         viewModel = viewModel,
         onNavigateToMemory = { id ->
             navController.navigate(Screen.MemoryDetail.createRoute(id))
         },
+        onBack = { navController.popBackStack() }
     )
 }
```

## Build Verification
```
./gradlew assembleDebug --quiet
BUILD SUCCESS
```

## General Rule
**Every screen reachable only via Dashboard tiles (not in bottom nav) MUST have BackHandler wired.** Audit pattern:
```bash
grep -r "BackHandler" android/app/src/main/java/dev/mazemaker/mobile/ui/screen/
# Should list every non-bottom-nav screen
```