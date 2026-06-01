import os
import subprocess
import ast

class CodeMutator:
    def __init__(self, repo_path="."):
        self.repo_path = repo_path

    def _run_cmd(self, cmd):
        result = subprocess.run(cmd, shell=True, cwd=self.repo_path, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def _vcs_prepare(self, branch_name):
        self._run_cmd("git checkout main")
        code, _, _ = self._run_cmd(f"git checkout -b {branch_name}")
        return code == 0

    def _vcs_finalize(self, branch_name, success, commit_msg="Swarm self-optimization"):
        if success:
            self._run_cmd("git add .")
            self._run_cmd(f'git commit -m "{commit_msg}"')
            self._run_cmd("git checkout main")
            self._run_cmd(f"git merge {branch_name}")
            self._run_cmd(f"git branch -d {branch_name}")
            return True
        else:
            self._run_cmd("git reset --hard HEAD")
            self._run_cmd("git checkout main")
            self._run_cmd(f"git branch -D {branch_name}")
            return False

    def mutate_function_ast(self, file_path, target_func_name, new_body_source):
        """
        WISDOM CHOICE: Class-aware method mutation that completely replaces the logic block.
        """
        mutation_id = f"ast-{int(os.times().elapsed)}"
        if not self._vcs_prepare(mutation_id):
            return False, "Failed to initialize git mutation branch."

        full_path = os.path.join(self.repo_path, file_path)
        
        try:
            with open(full_path, "r") as f:
                source = f.read()
            
            tree = ast.parse(source)
            new_body_ast = ast.parse(new_body_source).body[0].body  # Extract just the internal body statements

            modified = False
            # Look inside classes to find indented methods correctly
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_func_name:
                    node.body = new_body_ast
                    modified = True
                    break

            if not modified:
                raise ValueError(f"Function '{target_func_name}' not found in AST.")

            # Write back via modern built-in ast.unparse (zero dependencies needed for Python 3.9+)
            with open(full_path, "w") as f:
                f.write(ast.unparse(tree))

            # Validate syntax via compilation
            code, _, err = self._run_cmd(f"python3 -m py_compile {file_path}")
            if code != 0:
                raise SyntaxError(f"AST mutation introduced syntax errors: {err}")

            self._vcs_finalize(mutation_id, success=True, commit_msg=f"Optimized function: {target_func_name}")
            return True, f"Successfully mutated {target_func_name}."

        except Exception as e:
            self._vcs_finalize(mutation_id, success=False)
            return False, f"AST Mutation failed: {str(e)}"
