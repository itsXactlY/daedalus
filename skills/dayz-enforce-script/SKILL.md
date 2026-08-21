---
name: dayz-enforce-script
description: Enforce Script (DayZ) syntax constraints and common pitfalls - what does NOT exist in the language
category: dayz-mod-development
---

# Enforce Script Syntax Reference

## What Does NOT Exist

Enforce Script is NOT standard C#/C++/Java. Many common constructs are missing. Here are the critical differences:

### NO Array Bracket Syntax
**WRONG:**
```c
int[] myArray;
```
**CORRECT:**
```c
ref array<int> myArray = new array<int>;
myArray.Insert(42);
int val = myArray.Get(0);
myArray.Set(0, 99);
```

Use `ref array<T>` with methods: `Insert()`, `Get()`, `Set()`, `Count()`, `Remove()`.

### NO ref on Already-Ref-Counted Types
**WRONG:**
```c
ref PlayerIdentity identity;
```
**CORRECT:**
```c
PlayerIdentity identity;  // Already ref-counted by engine
```

`PlayerIdentity`, `PlayerBase`, and other engine types are already reference-counted. Adding `ref` causes issues.

### NO switch Statements
**WRONG:**
```c
switch (value) {
    case 1: doSomething(); break;
    case 2: doOther(); break;
}
```
**CORRECT:**
```c
if (value == 1) {
    doSomething();
} else if (value == 2) {
    doOther();
}
```

### NO Object Literal Syntax
**WRONG:**
```c
MyClass obj = { field1: "value", field2: 42 };
```
**CORRECT:**
```c
MyClass obj = new MyClass();
obj.field1 = "value";
obj.field2 = 42;
```

### NO Ternary Operator
**WRONG:**
```c
int result = (a > b) ? a : b;
```
**CORRECT:**
```c
int result;
if (a > b) {
    result = a;
} else {
    result = b;
}
```

### NO GetType() — with one important exception
**WRONG (custom class):**
```c
MyCustomClass obj = new MyCustomClass();
string typeName = obj.GetType();  // does NOT exist on custom classes
```

**CORRECT (custom class):**
```c
// Custom classes do not have reflection. Store the type name as a field
// if you need it, or compare by class:
if (obj.IsInherited(SomeBaseClass)) { /* ... */ }
```

**EXCEPTION — `Object.GetType()` IS valid:**
```c
EntityAI item = ...;
string className = item.GetType();   // WORKS — returns the class name
if (item.GetType() == "ChernarusMap") { /* ... */ }
```

`Object.GetType()` is an engine method that returns the class name as a string
for any engine object (`EntityAI`, `ItemBase`, `PlayerBase`, `Weapon`, etc.).
This is how you identify an object's class for inventory checks, currency
detection, marker-type comparison, etc. Use it freely.

The blanket "GetType() does not exist" rule from older DayZ mod guides is
**wrong for Object subclasses** — it only fails on custom script classes.
Don't remove `item.GetType()` calls in inventory / item-id code.

## ScriptRPC.Send Signature

```c
// Send(type, rpc, target, recipient)
//   type:    RPC type identifier
//   rpc:     ScriptRPC object
//   target:  MUST be null (no target object)
//   recipient: PlayerIdentity of recipient
rpc.Send(RPC_TYPE, rpc, null, playerIdentity);
```

**Critical:** First argument to Send must be `null` - there is no target object concept.

## Brace-Check Before Rebuild

**ALWAYS check brace matching before rebuilding.** A missing or extra brace causes:
- Compilation failure
- Cascading errors
- Failed build cycle after failed cycle
- Wasted time debugging phantom errors

Quick brace check:
```bash
# Count opening vs closing braces in your script
grep -c '{' file.c
grep -c '}' file.c
# Numbers should match
```

## Common Patterns

### Safe Array Iteration
```c
ref array<SomeType> items = GetItems();
for (int i = 0; i < items.Count(); i++) {
    SomeType item = items.Get(i);
    // process item
}
```

### Null-Safe Access
```c
if (someObject) {
    // safe to use
}
```

### RPC Communication
```c
// Sending
ScriptRPC rpc = new ScriptRPC();
rpc.Write(someValue);
rpc.Send(RPC_TYPE, rpc, null, targetIdentity);

// Receiving
void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx) {
    if (rpc_type == RPC_TYPE) {
        int value;
        ctx.Read(value);
        // process
    }
}
```

## Quick Reference

| Common Construct | Enforce Script Equivalent |
|-----------------|--------------------------|
| `int[]` | `ref array<int>` |
| `array[i]` | `array.Get(i)` / `array.Set(i, val)` |
| `switch/case` | `if/else if/else` |
| `?:` ternary | `if/else` |
| `{...}` literal | `new` + manual assignment |
| `obj.GetType()` (custom class) | Does not exist — use `IsInherited()` |
| `entity.GetType()` (Object subclass) | VALID — returns class name string |

## Debugging Tips

1. Syntax errors are often silent - check build output carefully
2. Missing braces cause cascading failures
3. Use `Print()` for debugging (no printf-style formatting)
4. Test small changes incrementally
