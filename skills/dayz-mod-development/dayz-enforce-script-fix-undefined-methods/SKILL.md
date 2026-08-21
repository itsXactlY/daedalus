---
name: dayz-enforce-script-fix-undefined-methods
description: Fixing undefined method errors in DayZ Enforce Script - getter/setter patterns
category: dayz-mod-development
tags: [dayz, enforce-script, undefined, methods, getter, setter, compilation]
---

# DayZ Enforce Script: Fix Undefined Methods in Custom Classes

## Problem
When developing DayZ mods with Enforce Script, accessing undefined methods on custom classes results in compilation errors. Commonly occurs when classes have private member variables but lack corresponding public getter/setter methods.

## Detection
- Compiler error: "Undefined function 'ClassName.MethodName'"
- Error occurs when trying to access methods like `IsMenuOpen()`, `GetVariable()` on custom classes
- The class typically has the backing private member variable but lacks the accessor methods
- Multiple files may attempt to call the same missing method

## Solution
1. Locate the class definition that's missing the method
2. Verify the backing private member variable exists
3. Add the missing getter and/or setter methods to the class
4. For boolean flags: add `GetFlagName()` returning the variable and `SetFlagName(bool)` setting it
5. Place methods near the end of the class definition before the closing brace

## Example Fix
For a class with `private bool m_IsMenuOpen;` missing `IsMenuOpen()`:
```c
bool IsMenuOpen() {
    return m_IsMenuOpen;
}

void SetMenuOpen(bool state) {
    m_IsMenuOpen = state;
}
```

## Prevention
- When adding private member variables that need external access, immediately add corresponding getter/setter methods
- Use consistent naming: `GetVariableName()` and `SetVariableName(type)`
- Review all files that instantiate the class to ensure they use the proper accessors
- Consider creating a template for common UI menu classes that need open/close state tracking

## Verification
- Recompile the mod to ensure no more undefined function errors
- Verify all call sites now work correctly
- Test the functionality that was previously broken due to the missing access

## DayZ Enforce Script Specifics
- Applies to classes extending `UIScriptedMenu` or other custom DayZ classes
- Commonly needed for menu state tracking, visibility flags, and UI interaction states
- Methods should be simple wrappers around member variables without additional logic

## Enhanced Solution Approach

### Phase 1: Discovery and Verification
1. **Identify the error location**: Note the file and line number from the compiler error
2. **Check filename casing**: DayZ file references may have different casing than expected (e.g., ClientManager.c vs clientmanager.c)
3. **Locate the class definition**: Find the class that's missing the method
4. **Verify member variable exists**: Confirm the backing private member variable is present
5. **Check all call sites**: Search for all occurrences of the missing method call to understand scope

### Phase 2: Apply DayZ Enforce Script Patterns
1. **Getter method**: For `private bool m_IsMenuOpen;` add `bool IsMenuOpen() { return m_IsMenuOpen; }`
2. **Setter method**: For `private bool m_IsMenuOpen;` add `void SetMenuOpen(bool state) { m_IsMenuOpen = state; }`
3. **Placement**: Add methods near the end of the class before the closing brace
4. **Naming convention**: Use `GetVariableName()` and `SetVariableName(type)` pattern

### Phase 3: Constraint Compliance Verification
Verify the fix adheres to DayZ Enforce Script constraints:
- ✅ **No switch statements**: Replace with if/else chains
- ✅ **No ternary operators**: Replace with if/else  
- ✅ **No array literals**: Use `ref array<T>` + Insert/Get/Set/.Count()
- ✅ **Proper foreach**: Avoid `foreach(key, value : map)` syntax
- ✅ **Function-level variable scope**: No redeclaring variables in nested blocks
- ✅ **Widget event handlers**: Proper `bool OnClick(Widget, int, int, int)` signatures

### Phase 4: Duplication Prevention
After applying the fix:
1. **Check for duplicates**: Search the file to ensure methods weren't accidentally duplicated
2. **Validate placement**: Ensure methods are in the correct location (after other methods, before closing brace)
3. **Verify naming consistency**: Confirm method names match the expected getter/setter pattern

### Phase 5: Multi-Call Site Validation
Test that all call sites now work:
1. **ClientManager.c**: `mapMenu.IsMenuOpen()` calls
2. **missionGameplay.c**: `m_VPPMapMenu.IsMenuOpen()` calls  
3. **Any other files**: Search for additional usages of the method
4. **Setter usage**: Verify `SetMenuOpen(bool)` calls work if applicable

## Example Fix Workflow
For the specific case of `VPPMapMenu.IsMenuOpen()`:

**Before:**
```c
class VPPMapMenu extends UIScriptedMenu {
    private bool m_IsMenuOpen;
    // ... other members and methods ...
    // MISSING: IsMenuOpen() and SetMenuOpen(bool) methods
}
```

**After applying fix:**
```c
class VPPMapMenu extends UIScriptedMenu {
    private bool m_IsMenuOpen;
    // ... other members and methods ...
    
    bool IsMenuOpen() {
        return m_IsMenuOpen;
    }

    void SetMenuOpen(bool state) {
        m_IsMenuOpen = state;
    }
}
```

## Prevention Strategies
1. **Immediate implementation**: When adding private member variables requiring external access, immediately add corresponding getter/setter methods
2. **Consistent naming**: Always use `GetVariableName()` and `SetVariableName(type)` patterns
3. **Module awareness**: Remember DayZ module load order (3_Game → 4_World → 5_Mission) and cross-visibility rules
4. **Template creation**: Create templates for common UI menu classes needing state tracking

## Verification Checklist
- [ ] Compiler error "Undefined function 'ClassName.MethodName'" resolved
- [ ] Getter method returns correct member variable type and value
- [ ] Setter method correctly assigns to member variable
- [ ] No switch statements, ternary operators, or array literals introduced
- [ ] Methods placed correctly in class definition (before closing brace)
- [ ] No duplicate methods created
- [ ] All call sites accessing the method now compile successfully
- [ ] Follows function-level variable scope rules
- [ ] Complies with DayZ module cross-visibility constraints

## DayZ-Specific Considerations
- **UIScriptedMenu classes**: Commonly need open/close state tracking for menus
- **Cross-module access**: Ensure calling module can see the class definition (based on load order)
- **Private member access**: Other classes cannot access private members directly - must use getters/setters
- **Method simplicity**: Keep getters/setters as simple wrappers without additional business logic