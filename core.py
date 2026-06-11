import functools
from typing import Any, Callable
import time

def validate_payload(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to strictly enforce that the dictionary key is a string.
    Intercepts the call, checks the type of the 'key' argument, 
    and either raises a TypeError or proceeds with the original function.
    """
    @functools.wraps(func)
    def inner(self, key: str, *args: Any, **kwargs: Any) -> Any:
        if type(key) is not str:
            raise TypeError("the key in CoreDB objects must be str")
        if args:
            value = args[0]

            if type(value) is not self.value_type:
                raise TypeError(f"Value must be strictly {self._value_type.__name__}")
        
        return func(self, key, *args, **kwargs)
    return inner


class CoreDB:
    """
    In-memory Key-Value store engine designed with strict 
    type hinting and architectural safety mechanisms.
    """
    def __init__(self, value_type: type):
        self._store: dict[str, Any] = {}
        self._value_type = value_type
        self._backup: dict[str, Any] | None = None
        self._log_path: str = "db_log.txt"
        self._recover()
    
    @property
    def size(self) -> int:
        return len(self._store)
    @property
    def value_type(self) -> Any:
        return self._value_type
    

    @validate_payload
    def __setitem__(self, key: str, value: Any) -> None:
        """
        Inserts or updates a key-value pair in the database.
        """
        self._store[key] = value
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(f"SET {key} {value}\n")


    @validate_payload
    def __getitem__(self, key: str) -> Any:
        """
        Retrieves a value by its key. Returns None and prints a warning 
        if the key does not exist to prevent system crashes.
        """
        val = self._store.get(key)
        if val is None and key not in self._store:
            print("warning key is not in self._store")
            return None
        return val

    @validate_payload
    def __delitem__(self, key: str) -> None:
        """
        Deletes a key-value pair. Fails silently if the key does not exist.
        """
        if key in self._store:
            self._store.pop(key)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"DEL {key}\n")

        

    @validate_payload
    def __contains__(self, key: str) -> bool:
        """
        Checks for the existence of a key in the database natively using 'in'.
        """
        return key in self._store
    
    def clear(self) -> None:
        self._store.clear()
        with open(self._log_path, "w", encoding="utf-8") as f:
            pass

    def __len__(self) -> int:
        return self.size

    def __bool__(self) -> bool:
        return bool(self._store) 

    def __enter__(self):
        self._backup = self._store.copy()
        return self
    
    def __exit__(self, exc_type, exc_val, traceback):
        if exc_type:
            self._store = self._backup
            print("[Rollback]: Transaction failed, reverting database to previous state")
        self._backup = None

    def _read_log_lazily(self):
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for l in f:
                    yield l.strip()
        except FileNotFoundError:
            return

    def _recover(self):
        for l in self._read_log_lazily():
            tokens = l.split(maxsplit=2)
            if tokens[0] == "SET":
                value = self._value_type(tokens[2])
                self._store[tokens[1]] = value
            elif tokens[0] == "DEL":
                self._store.pop(tokens[1])


    def find(self, condition: Callable[[Any], bool]) -> dict[str, Any]:
        return (dict(filter(lambda x: condition(x[1]), self._store.items())))
    
    def __iter__(self):
        return iter(self._store)

class VolatileDB(CoreDB):
    def __init__(self, value_type: type, ttl_seconds: int):
        super().__init__(value_type)
        self._ttl = ttl_seconds
        self._timestamps: dict[str, float] = {}

    def __setitem__(self, key: str, value: Any) -> None:
        self._timestamps[key] = time.time()
        super().__setitem__(key, value)

    def __getitem__(self, key: str):
        try:
            t = time.time() - self._timestamps[key]
            if t > self._ttl:
                self._timestamps.pop(key)
                super().__delitem__(key)
                return None
            else:
                return super().__getitem__(key)
        except KeyError:
            return None

    
