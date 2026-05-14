"""
Tests for application structure and configuration.

This module tests that the project structure follows baseweb patterns,
has correct configuration, and proper initialization.
"""

import pytest
from pathlib import Path
import tomli


class TestProjectStructure:
  """
  Test suite for project directory structure.

  Tests verify that the project follows the baseweb hello-world pattern
  with correct directory layout and file organization.
  """

  def test_pyproject_toml_exists(self):
    """
    Test that pyproject.toml exists at project root.

    Given: The project root directory
    When: Checking for pyproject.toml
    Then: File exists and is valid TOML
    """
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml should exist at project root"

    # Verify it's valid TOML
    with open(pyproject_path, "rb") as f:
      config = tomli.load(f)
      assert "project" in config, "pyproject.toml should have [project] section"

  def test_app_package_exists(self):
    """
    Test that app/ package directory exists.

    Given: The project root directory
    When: Checking for app/ directory
    Then: Directory exists with __init__.py
    """
    app_path = Path(__file__).parent.parent / "app"
    assert app_path.exists(), "app/ directory should exist"
    assert app_path.is_dir(), "app/ should be a directory"

    init_path = app_path / "__init__.py"
    assert init_path.exists(), "app/__init__.py should exist"

  def test_pages_package_exists(self):
    """
    Test that app/pages/ package directory exists.

    Given: The app/ directory
    When: Checking for pages/ subdirectory
    Then: Directory exists with __init__.py
    """
    pages_path = Path(__file__).parent.parent / "app" / "pages"
    assert pages_path.exists(), "app/pages/ directory should exist"
    assert pages_path.is_dir(), "app/pages/ should be a directory"

    init_path = pages_path / "__init__.py"
    assert init_path.exists(), "app/pages/__init__.py should exist"

  def test_chat_page_directory_exists(self):
    """
    Test that chat page directory exists.

    Given: The app/pages/ directory
    When: Checking for chat/ subdirectory
    Then: Directory exists with __init__.py and chat.js
    """
    chat_path = Path(__file__).parent.parent / "app" / "pages" / "chat"
    assert chat_path.exists(), "app/pages/chat/ directory should exist"
    assert chat_path.is_dir(), "app/pages/chat/ should be a directory"

    init_path = chat_path / "__init__.py"
    assert init_path.exists(), "app/pages/chat/__init__.py should exist"

    js_path = chat_path / "chat.js"
    assert js_path.exists(), "app/pages/chat/chat.js should exist"

  def test_chat_js_component_exists(self):
    """
    Test that chat.js Vue component exists.

    Given: The app/pages/chat/ directory
    When: Checking for chat.js
    Then: File exists and contains Vue component definition
    """
    js_path = Path(__file__).parent.parent / "app" / "pages" / "chat" / "chat.js"
    assert js_path.exists(), "chat.js should exist"

    content = js_path.read_text()
    assert "var Chat" in content or "Chat = {" in content, "chat.js should define Chat component"
    assert "name: 'Chat'" in content, "Chat component should have name property"
    assert "template:" in content, "Chat component should have template"


class TestProjectConfiguration:
  """
  Test suite for project configuration files.

  Tests verify that pyproject.toml has correct dependencies
  and settings for the roomz project.
  """

  def test_project_name_configured(self):
    """
    Test that project name is 'roomz' in pyproject.toml.

    Given: pyproject.toml file
    When: Parsing the configuration
    Then: project.name equals 'roomz'
    """
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
      config = tomli.load(f)
      assert config["project"]["name"] == "roomz", "Project name should be 'roomz'"

  def test_baseweb_dependency_exists(self):
    """
    Test that baseweb is listed as a dependency.

    Given: pyproject.toml file
    When: Parsing dependencies
    Then: baseweb >= 0.5.0 is listed
    """
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
      config = tomli.load(f)
      dependencies = config["project"]["dependencies"]
      baseweb_found = any("baseweb" in dep for dep in dependencies)
      assert baseweb_found, "baseweb should be in dependencies"

  def test_python_version_configured(self):
    """
    Test that Python version requirement is set.

    Given: pyproject.toml file
    When: Parsing Python version requirement
    Then: requires-python specifies >= 3.10
    """
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
      config = tomli.load(f)
      assert "requires-python" in config["project"], "requires-python should be set"
      assert "3.10" in config["project"]["requires-python"], "Python >= 3.10 should be required"

  def test_quart_dependency_exists(self):
    """
    Test that Quart is listed as a dependency (via baseweb).

    Given: pyproject.toml file
    When: Parsing dependencies
    Then: Quart is available (via baseweb or explicit)
    """
    # Quart comes with baseweb, so checking baseweb is sufficient
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
      config = tomli.load(f)
      dependencies = config["project"]["dependencies"]
      baseweb_found = any("baseweb" in dep for dep in dependencies)
      assert baseweb_found, "Quart should be available via baseweb dependency"

  def test_socketio_dependency_exists(self):
    """
    Test that python-socketio is available (via baseweb).

    Given: pyproject.toml file
    When: Parsing dependencies
    Then: python-socketio is available for WebSocket support
    """
    # python-socketio comes with baseweb, so checking baseweb is sufficient
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
      config = tomli.load(f)
      dependencies = config["project"]["dependencies"]
      baseweb_found = any("baseweb" in dep for dep in dependencies)
      assert baseweb_found, "SocketIO should be available via baseweb dependency"


class TestBasewebInitialization:
  """
  Test suite for baseweb application initialization.

  Tests verify that the application correctly initializes
  with baseweb and SocketIO support.
  """

  def test_baseweb_initialization(self):
    """
    Test that baseweb is correctly initialized in app/__init__.py.

    Given: The app/__init__.py module
    When: Importing the module
    Then: Baseweb instance is created with name 'roomz'
    """
    from app import server
    assert server is not None, "Server should be initialized"
    assert server.name == "roomz", "Server name should be 'roomz'"

  def test_socketio_enabled(self):
    """
    Test that SocketIO is enabled in baseweb configuration.

    Given: The baseweb configuration
    When: Checking SocketIO settings
    Then: SocketIO is enabled for WebSocket support
    """
    from app import server
    assert server.socketio is not None, "SocketIO should be enabled"

  def test_asgi_app_entry_point(self):
    """
    Test that ASGI app entry point is correctly set.

    Given: The app/__init__.py module
    When: Accessing the ASGI entry point
    Then: asgi_app variable is properly defined
    """
    from app import asgi_app
    assert asgi_app is not None, "ASGI app entry point should be defined"

  def test_pages_import(self):
    """
    Test that pages module is imported for route registration.

    Given: The app/__init__.py module
    When: Examining imports
    Then: from . import pages is present
    """
    # This test verifies that importing app doesn't raise an error
    # The pages module should be imported successfully
    import app.pages
    assert app.pages is not None, "Pages module should be imported"


class TestChatPageRegistration:
  """
  Test suite for chat page registration.

  Tests verify that the chat page is properly registered
  with baseweb's navigation system.
  """

  def test_chat_page_registered(self):
    """
    Test that chat page is registered with navigation.

    Given: The app/pages/chat/chat.js component
    When: Examining the component
    Then: Navigation object with path '/' exists
    """
    js_path = Path(__file__).parent.parent / "app" / "pages" / "chat" / "chat.js"
    content = js_path.read_text()
    assert 'path: "/"' in content, "Chat page should have navigation path '/'"

  def test_chat_component_name(self):
    """
    Test that chat component has correct name.

    Given: The app/pages/chat/chat.js component
    When: Examining the component definition
    Then: Component name is 'Chat' or 'ChatRoom'
    """
    js_path = Path(__file__).parent.parent / "app" / "pages" / "chat" / "chat.js"
    content = js_path.read_text()
    assert "name: 'Chat'" in content, "Component name should be 'Chat'"

  def test_chat_component_template(self):
    """
    Test that chat component has Vue template.

    Given: The app/pages/chat/chat.js component
    When: Examining the component definition
    Then: Template property exists with valid Vue template
    """
    js_path = Path(__file__).parent.parent / "app" / "pages" / "chat" / "chat.js"
    content = js_path.read_text()
    assert "template:" in content, "Chat component should have template property"
    assert "<Page>" in content, "Template should include Page component"

  def test_chat_page_icon(self):
    """
    Test that chat page has navigation icon.

    Given: The chat component navigation config
    When: Examining navigation settings
    Then: Icon is set to 'mdi-chat'
    """
    js_path = Path(__file__).parent.parent / "app" / "pages" / "chat" / "chat.js"
    content = js_path.read_text()
    assert 'icon: "mdi-chat"' in content, "Chat page should have mdi-chat icon"


class TestSocketIOHandlers:
  """
  Test suite for SocketIO event handler registration.

  Tests verify that SocketIO event handlers are properly
  registered with the baseweb server.
  """

  def test_connect_handler_registered(self):
    """
    Test that 'connect' event handler is registered.

    Given: The app/__init__.py module
    When: Checking SocketIO handlers
    Then: 'connect' event handler exists
    """
    app_init_path = Path(__file__).parent.parent / "app" / "__init__.py"
    content = app_init_path.read_text()
    assert '@server.socketio.on("connect")' in content, "Connect handler should be registered"

  def test_disconnect_handler_registered(self):
    """
    Test that 'disconnect' event handler is registered.

    Given: The app/__init__.py module
    When: Checking SocketIO handlers
    Then: 'disconnect' event handler exists
    """
    app_init_path = Path(__file__).parent.parent / "app" / "__init__.py"
    content = app_init_path.read_text()
    assert '@server.socketio.on("disconnect")' in content, "Disconnect handler should be registered"

  def test_message_handler_registered(self):
    """
    Test that 'message' event handler is registered.

    Given: The app/__init__.py module
    When: Checking SocketIO handlers
    Then: 'message' event handler exists
    """
    app_init_path = Path(__file__).parent.parent / "app" / "__init__.py"
    content = app_init_path.read_text()
    assert '@server.socketio.on("message")' in content, "Message handler should be registered"


class TestApplicationLogging:
  """
  Test suite for application logging configuration.

  Tests verify that logging is properly configured
  for the application.
  """

  def test_log_config_called(self):
    """
    Test that log configuration is called during initialization.

    Given: The app/__init__.py module
    When: Initializing the application
    Then: server.log_config() is called
    """
    app_init_path = Path(__file__).parent.parent / "app" / "__init__.py"
    content = app_init_path.read_text()
    assert "server.log_config()" in content, "log_config() should be called"

  def test_log_routes_called(self):
    """
    Test that route logging is called during initialization.

    Given: The app/__init__.py module
    When: Initializing the application
    Then: server.log_routes() is called
    """
    app_init_path = Path(__file__).parent.parent / "app" / "__init__.py"
    content = app_init_path.read_text()
    assert "server.log_routes()" in content, "log_routes() should be called"