"""Docker sandbox execution environment for TermMind."""

try:
    import docker
except ImportError:
    docker = None

class DockerSandbox:
    """Provides an isolated environment for safe code execution."""

    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image
        self.client = docker.from_env() if docker else None

    def is_available(self) -> bool:
        return self.client is not None

    def execute_script(self, script_code: str, timeout: int = 15) -> str:
        """Run a python script securely inside a container."""
        if not self.is_available():
            return "Error: Docker SDK not available. Install 'docker' module."

        try:
            container = self.client.containers.run(
                self.image,
                command=["python", "-c", script_code],
                detach=True,
                mem_limit="128m",
                network_disabled=True
            )
            try:
                result = container.wait(timeout=timeout)
                logs = container.logs().decode("utf-8")
                if result['StatusCode'] != 0:
                    return f"Execution failed (Code {result['StatusCode']}):\n{logs}"
                return logs
            except Exception as e:
                container.kill()
                return f"Execution timeout or error: {e}"
            finally:
                container.remove(force=True)
        except Exception as e:
            return f"Container startup error: {e}"
