# CloakChat Tests

This directory contains tests for the CloakChat project.

## Structure

- `tests/test_*.py`: Python tests for the FastAPI backend and core pipeline logic.
- `frontend/tests/`: Vitest/React Testing Library tests for the UI components and stores.

## Running Tests

### Backend Tests

```bash
# Ensure you are in the project root
pytest
```

### Frontend Tests

```bash
cd frontend
bun test
```

## Coverage

We aim for high coverage on core anonymization logic. Ensure any new features in `core/` are accompanied by relevant unit tests.
