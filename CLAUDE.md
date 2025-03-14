# CLAUDE.md - Guidelines for Spot Server Project

## Build and Test Commands
```
# Run development server
make dev

# Install dependencies
make install

# Run all tests
make test

# Run a single test file
pytest path/to/test_file.py

# Run a specific test
pytest path/to/test_file.py::test_function_name

# Code quality
make lint  # runs flake8 and black
```

## Code Style Guidelines
- **Python**: Follow PEP 8 style guide
- **Type hints**: Use typing module for all function parameters and returns
- **Imports**: Group standard library, third-party, and local imports
- **Logging**: Use the configured logger, not print statements
- **Error handling**: Use try/except blocks with specific exceptions
- **Async**: Project uses async/await pattern with FastAPI
- **Data models**: Use Pydantic BaseModel for data validation
- **Documentation**: Include docstrings for all functions and classes
- **Testing**: Write tests for new functionality
- **Environment variables**: Use app.config for configuration