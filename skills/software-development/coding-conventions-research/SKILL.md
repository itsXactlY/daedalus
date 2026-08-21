---
name: coding-conventions-research
description: Comprehensive coding conventions from top repos - SOLID, design patterns, error handling, naming, DDD
category: software-development
version: 1.0
tags: [oop, solid, design-patterns, conventions, python, javascript, rust]
---

# Coding Conventions Research

Based on research from GitHub's most-starred repos (clean-code-python 4779★, python-patterns 42k★, node-best-practices, Google Python Style, Airbnb JS, Rust API Guidelines, System Design Primer).

## SOLID Principles

### SRP (Single Responsibility)
A class should have ONE reason to change. If you describe it with 'and', it violates SRP.
Separate fetching from rendering, data from logic.

### OCP (Open/Closed)
Open for extension, closed for modification. Use Template Method + Mixins.

### LSP (Liskov Substitution)
Subtypes must preserve supertype signatures. Override extension points only. Use mypy.

### ISP (Interface Segregation)
Keep interfaces small. Clients shouldn't depend on unused methods. Use ABCMeta + @abstractmethod.

### DIP (Dependency Inversion)
Depend on abstractions. Leverage duck typing - csv.writer needs .write(), pass any object with that method.

## Design Patterns (Python)
- **Creational**: abstract_factory, borg (shared-state singleton), builder, factory, lazy_evaluation, pool, prototype
- **Structural**: 3-tier, adapter, bridge, composite, decorator, facade, flyweight, front_controller, mvc, proxy
- **Behavioral**: chain_of_responsibility, command, iterator, mediator, memento, observer, publish_subscribe, state, strategy, template, visitor

## Anti-Patterns to AVOID
1. Singleton - Python modules ARE already singletons
2. God Object - too much logic in one class
3. Inheritance overuse - prefer composition ("Favor composition over inheritance")

## Error Handling
- Distinguish operational (ValidationError) vs catastrophic (uncaughtException)
- Centralize error handling in ErrorHandler class
- Extend built-in Error class with AppError (name, message, cause, isCatastrophic)
- Validate early with schema libraries (Zod, Pydantic)

## Naming Conventions
- Classes: PascalCase
- Functions/methods: snake_case
- Constants: UPPER_SNAKE_CASE
- Private: _leading_underscore
- Boolean: is_, has_, should_ prefix

## Source: convention_research/CODING_CONVENTIONS_FINDINGS.md in The Architects Palace