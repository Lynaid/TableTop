import ast
import random


class ScriptSecurityError(Exception):
    pass


class RulesEngine:
    """
    Mini rule/scripting engine.

    - Converts Lua-like syntax to restricted Python.
    - Validates AST against a whitelist of safe nodes.
    - Executes with a safe environment (no builtins).
    - Provides helper functions: roll, damage, heal, move, say, set, trigger.
    - Stores global scripts per event_type in self.global_scripts.
    """

    def __init__(self, say_callback=None, max_trigger_depth=3):
        self.say_callback = say_callback
        self.max_trigger_depth = max_trigger_depth
        self.global_scripts = {}  # event_type -> script string

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def run_event(self, event_type, token=None, tile=None, event_data=None, depth=0):
        """
        Execute all scripts bound to this event type:

        1) token.scripts[event_type]
        2) tile.trigger['script'] if tile.trigger['type'] matches event_type
        3) global_scripts[event_type]

        event_data is an optional dict with extra info.
        """
        if depth > self.max_trigger_depth:
            return

        event = {
            "type": event_type,
            "data": event_data or {},
        }

        # token script
        if token is not None and getattr(token, "scripts", None):
            script = token.scripts.get(event_type)
            if script:
                self._run_single_script(script, token, tile, event, depth)

        # tile trigger (for tile events only)
        if tile is not None:
            trigger = getattr(tile, "trigger", None)
            if isinstance(trigger, dict):
                trig_type = trigger.get("type")
                trig_script = trigger.get("script")
                once = bool(trigger.get("once", False))
                fired = bool(trigger.get("fired", False))

                # Map tile trigger type to event types
                # "onEnter"  -> event_type == "onEnterTile"
                # "onLeave"  -> event_type == "onLeaveTile"
                # "onInteract" -> event_type == "onInteractTile"
                match = False
                if trig_type == "onEnter" and event_type == "onEnterTile":
                    match = True
                elif trig_type == "onLeave" and event_type == "onLeaveTile":
                    match = True
                elif trig_type == "onInteract" and event_type == "onInteractTile":
                    match = True

                if match and trig_script and (not once or not fired):
                    self._run_single_script(trig_script, token, tile, event, depth)
                    if once:
                        trigger["fired"] = True

        # global scripts
        script = self.global_scripts.get(event_type)
        if script:
            self._run_single_script(script, token, tile, event, depth)

    def set_global_script(self, event_type, script):
        self.global_scripts[event_type] = script or ""

    def to_json(self):
        return {
            "global": dict(self.global_scripts),
        }

    def load_from_json(self, data):
        if not isinstance(data, dict):
            return
        g = data.get("global", {})
        if isinstance(g, dict):
            self.global_scripts = dict(g)

    # ------------------------------------------------------------------
    # INTERNAL: script execution pipeline
    # ------------------------------------------------------------------

    def _run_single_script(self, script, token, tile, event, depth):
        script = script or ""
        if not script.strip():
            return

        # Prepare environment
        env = {}
        env_token = token
        env_tile = tile
        env_event = event

        # Bind basic vars from token
        if env_token is not None:
            try:
                env["hp"] = float(env_token.hp)
            except Exception:
                env["hp"] = 0.0
            try:
                env["max_hp"] = float(env_token.max_hp)
            except Exception:
                env["max_hp"] = env["hp"]
            env["x"] = float(env_token.x)
            env["y"] = float(env_token.y)
            env["name"] = str(env_token.name)
            tnt = getattr(env_token, "tint", (1.0, 1.0, 1.0))
            if not isinstance(tnt, (list, tuple)) or len(tnt) != 3:
                tnt = (1.0, 1.0, 1.0)
            env["tint"] = [float(tnt[0]), float(tnt[1]), float(tnt[2])]
        else:
            env["hp"] = 0.0
            env["max_hp"] = 0.0
            env["x"] = 0.0
            env["y"] = 0.0
            env["name"] = ""
            env["tint"] = [1.0, 1.0, 1.0]

        env["token"] = env_token
        env["tile"] = env_tile
        env["event"] = env_event

        # Functions
        def roll_fn(n):
            try:
                n = int(n)
            except Exception:
                n = 1
            if n < 1:
                n = 1
            return random.randint(1, n)

        def damage_fn(n):
            try:
                n = float(n)
            except Exception:
                n = 0.0
            env["hp"] = max(0.0, env["hp"] - n)

        def heal_fn(n):
            try:
                n = float(n)
            except Exception:
                n = 0.0
            env["hp"] = min(env["max_hp"], env["hp"] + n)

        def move_fn(dx, dy):
            try:
                dx = float(dx)
                dy = float(dy)
            except Exception:
                dx = 0.0
                dy = 0.0
            env["x"] += dx
            env["y"] += dy

        def say_fn(text):
            msg = str(text)
            if self.say_callback:
                self.say_callback(msg)
            else:
                print(f"[SAY] {msg}")

        def set_fn(var, value):
            if not isinstance(var, str):
                return
            env[var] = value

        def trigger_fn(name):
            # trigger("onDeath") etc.
            name = str(name)
            self.run_event(name, env_token, env_tile, env_event["data"], depth + 1)

        env["roll"] = roll_fn
        env["damage"] = damage_fn
        env["heal"] = heal_fn
        env["move"] = move_fn
        env["say"] = say_fn
        env["set"] = set_fn
        env["trigger"] = trigger_fn

        # Build safe environment (no builtins)
        globals_dict = {"__builtins__": None}
        locals_dict = env

        # Translate mini-lang to Python, validate AST, execute
        py_code = self._to_python_code(script)
        self._validate_ast(py_code)
        old_hp = env["hp"]
        exec(py_code, globals_dict, locals_dict)  # no builtins, restricted env

        # propagate back to token
        if env_token is not None:
            try:
                env_token.x = float(env.get("x", env_token.x))
                env_token.y = float(env.get("y", env_token.y))
            except Exception:
                pass

            try:
                new_hp = float(env.get("hp", env_token.hp))
            except Exception:
                new_hp = env_token.hp
            try:
                new_max_hp = float(env.get("max_hp", env_token.max_hp))
            except Exception:
                new_max_hp = env_token.max_hp
            if new_max_hp < 1:
                new_max_hp = 1.0
            if new_hp < 0:
                new_hp = 0.0
            if new_hp > new_max_hp:
                new_hp = new_max_hp
            env_token.max_hp = int(new_max_hp)
            env_token.hp = int(new_hp)

            # tint
            t = env.get("tint", env_token.tint)
            if isinstance(t, (list, tuple)) and len(t) == 3:
                try:
                    r = float(t[0])
                    g = float(t[1])
                    b = float(t[2])
                except Exception:
                    r, g, b = 1.0, 1.0, 1.0
                env_token.tint = (
                    max(0.0, min(1.0, r)),
                    max(0.0, min(1.0, g)),
                    max(0.0, min(1.0, b)),
                )

        # onHPChange / onDeath triggers
        if env_token is not None:
            if env_token.hp != int(old_hp):
                self.run_event("onHPChange", env_token, env_tile, env_event["data"], depth + 1)
            if env_token.hp <= 0:
                self.run_event("onDeath", env_token, env_tile, env_event["data"], depth + 1)

    # ------------------------------------------------------------------
    # MINI-LANG -> PYTHON TRANSLATION
    # ------------------------------------------------------------------

    def _to_python_code(self, script):
        """
        Convert Lua-like:

            if hp < 10 then
                hp = hp + 2
            end

        to Python:

            if hp < 10:
                hp = hp + 2
        """
        lines = script.splitlines()
        out = []
        indent = 0

        for raw in lines:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("--"):
                continue

            if stripped.startswith("if ") and stripped.endswith(" then"):
                cond = stripped[3:-5].strip()
                out.append(" " * (indent * 4) + f"if {cond}:")
                indent += 1
            elif stripped == "else":
                indent = max(0, indent - 1)
                out.append(" " * (indent * 4) + "else:")
                indent += 1
            elif stripped == "end":
                indent = max(0, indent - 1)
            else:
                out.append(" " * (indent * 4) + stripped)

        return "\n".join(out)

    # ------------------------------------------------------------------
    # AST VALIDATION
    # ------------------------------------------------------------------

    def _validate_ast(self, code):
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as e:
            raise ScriptSecurityError(f"Syntax error in script: {e}") from e

        allowed_nodes = (
            ast.Module,
            ast.Expr,
            ast.Assign,
            ast.AugAssign,
            ast.BinOp,
            ast.UnaryOp,
            ast.BoolOp,
            ast.Compare,
            ast.If,
            ast.Call,
            ast.Load,
            ast.Store,
            ast.Name,
            ast.Constant,
            ast.Subscript,  # only for simple x[0], we still check attributes separately
            ast.Index,
            ast.Slice,
            ast.keyword,
            ast.Tuple,
            ast.List,
        )

        forbidden = (
            ast.Import,
            ast.ImportFrom,
            ast.For,
            ast.While,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.With,
            ast.Lambda,
            ast.Try,
            ast.Raise,
            ast.Global,
            ast.Nonlocal,
            ast.Attribute,
            ast.Dict,
            ast.ListComp,
            ast.DictComp,
            ast.SetComp,
            ast.GeneratorExp,
            ast.Await,
            ast.Yield,
            ast.YieldFrom,
        )

        for node in ast.walk(tree):
            if isinstance(node, forbidden):
                raise ScriptSecurityError(f"Forbidden construct: {type(node).__name__}")
            if not isinstance(node, allowed_nodes):
                raise ScriptSecurityError(f"Disallowed AST node: {type(node).__name__}")

        return True
