<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->


### TOOL GUIDELINES:
* Handling Long-Running Processes
  Some commands (like starting servers) may not terminate automatically. Always ensure commands have appropriate termination conditions or run in backgrounds that don't block execution. Assess whether a process needs to remain running or should be terminated after completion, and handle accordingly based on the specific context and requirements.



<!-- MEMSPEC:START -->
* Read .agents/learnings.md and .agents/learnings.json before starting any task.
<!-- MEMSPEC:END -->




## General

- Prioritize existing libraries and SDKs to leverage proven solutions.
- Use modern, well-maintained libraries with comprehensive documentation.
- Code should be **simple**, **intuitive**, and **minimal**, while being composable and extendable yet easy to read and understand.
- Create custom wrappers over external libraries to enable easy library swapping with minimal code changes.
- Use JSON for configuration and data files; use JSONC when comments are needed.
- Maintain ultra modular architecture with extreme separation of concerns. Keep modules independent to avoid confusing AI agents, even if it means some code duplication.
- Create abstraction layers to isolate core business logic from implementation details.
- Design through interfaces first - define clear contracts before implementing functionality.
- Build small, focused components that can be easily composed together.
- Keep core logic clean and implementation-agnostic; push technical details to dedicated wrapper modules.
- When integrating external services, create adapter patterns that abstract away third-party specifics.
- Write code as if it will be maintained by other AI agents - be explicit, consistent, and avoid clever tricks.
- Follow the "single responsibility principle" strictly - each module should do one thing well.
- Document architectural decisions and abstraction boundaries clearly.
- Error handling should be abstracted away from business logic whenever possible.
- Configuration and environment-specific code should be cleanly separated from core functionality.

### File Organization

- **Single file limit**: No file should exceed 300 lines of code. If approaching this limit, refactor into multiple focused files.
- **Use packages/modules**: Group related files into packages based on domain or functionality.
- **Hierarchical structure**: Create clear hierarchy: domain → sub-domain → specific functionality. Keep nesting minimal (max 3 levels deep unless absolutely necessary).
- **Package API**: Define the public interface of each package, explicitly exporting only what should be used externally.
- **Folder naming**: Use lowercase, descriptive names that clearly indicate the domain.
- **Avoid deep nesting**: Prefer flatter folder structures (sibling packages) over deeply nested packages. Deep nesting should only be used when it significantly improves logical organization.
- **Break up large files**: When a file grows beyond 200 lines, proactively split it into logical sub-modules within an appropriate package.
- **Keep imports clean**: Avoid circular dependencies by maintaining clear hierarchical relationships between packages.

### Python

- For Python projects, use uv and .venv for dependency and environment management.
- Use type hints consistently to make code more self-documenting and maintainable.
- Prefer composition over inheritance for creating reusable components.
- Follow PEP 8 style guidelines for consistent formatting.
- **Python packages**: Use folders with `__init__.py` files to create packages.
- **Public API**: Use `__all__` in `__init__.py` to explicitly control what is exported from packages.
- **Import style**: Use absolute imports within the project for clarity (e.g., `from myproject.data_access import UserStore` rather than relative imports).


### Markdown
- Utilise Mermaid diagrams for visual explanations of architecture, workflows, and processes.
- Use fenced code blocks with appropriate language tags for code snippets.
