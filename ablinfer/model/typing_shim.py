import collections
import typing
from typing import Generic

if hasattr(typing, "get_args"):
    from typing import get_args, get_origin
else:
    ## https://stackoverflow.com/questions/49171189/whats-the-correct-way-to-check-if-an-object-is-a-typing-generic
    if hasattr(typing, '_GenericAlias'):
        # python 3.7
        def _is_generic(cls):
            if isinstance(cls, typing._GenericAlias):
                return True

            if isinstance(cls, typing._SpecialForm):
                return cls not in {typing.Any}

            return False


        def _is_base_generic(cls):
            if isinstance(cls, typing._GenericAlias):
                if cls.__origin__ in {typing.Generic, typing._Protocol}:
                    return False

                if isinstance(cls, typing._VariadicGenericAlias):
                    return True

                return len(cls.__parameters__) > 0

            if isinstance(cls, typing._SpecialForm):
                return cls._name in {'ClassVar', 'Union', 'Optional'}

            return False
    else:
        # python <3.7
        if hasattr(typing, '_Union'):
            # python 3.6
            def _is_generic(cls):
                if isinstance(cls, (typing.GenericMeta, typing._Union, typing._Optional, typing._ClassVar)):
                    return True

                return False


            def _is_base_generic(cls):
                if isinstance(cls, (typing.GenericMeta, typing._Union)):
                    return cls.__args__ in {None, ()}

                if isinstance(cls, typing._Optional):
                    return True

                return False
        else:
            # python 3.5
            def _is_generic(cls):
                if isinstance(cls, (typing.GenericMeta, typing.UnionMeta, typing.OptionalMeta, typing.CallableMeta, typing.TupleMeta)):
                    return True

                return False


            def _is_base_generic(cls):
                if isinstance(cls, typing.GenericMeta):
                    return all(isinstance(arg, typing.TypeVar) for arg in cls.__parameters__)

                if isinstance(cls, typing.UnionMeta):
                    return cls.__union_params__ is None

                if isinstance(cls, typing.TupleMeta):
                    return cls.__tuple_params__ is None

                if isinstance(cls, typing.CallableMeta):
                    return cls.__args__ is None

                if isinstance(cls, typing.OptionalMeta):
                    return True

                return False


    def is_generic(cls):
        """
        Detects any kind of generic, for example `List` or `List[int]`. This includes "special" types like
        Union and Tuple - anything that's subscriptable, basically.
        """
        return _is_generic(cls)


    def is_base_generic(cls):
        """
        Detects generic base classes, for example `List` (but not `List[int]`)
        """
        return _is_base_generic(cls)


    def is_qualified_generic(cls):
        """
        Detects generics with arguments, for example `List[int]` (but not `List`)
        """
        return is_generic(cls) and not is_base_generic(cls)

    def get_args(tp):
        """Get type arguments with all substitutions performed.
        For unions, basic simplifications used by Union constructor are performed.
        Examples::
            get_args(Dict[str, int]) == (str, int)
            get_args(int) == ()
            get_args(Union[int, Union[T, int], str][int]) == (int, str)
            get_args(Union[int, Tuple[T, int]][str]) == (int, Tuple[str, int])
            get_args(Callable[[], T][int]) == ([], int)
        """
        if is_qualified_generic(tp):
            res = tp.__args__
            if get_origin(tp) is collections.abc.Callable and res[0] is not Ellipsis:
                res = (list(res[:-1]), res[-1])
            return res
        return ()

    def get_origin(tp):
        """Get the unsubscripted version of a type.
        This supports generic types, Callable, Tuple, Union, Literal, Final and ClassVar.
        Return None for unsupported types. Examples::
            get_origin(Literal[42]) is Literal
            get_origin(int) is None
            get_origin(ClassVar[int]) is ClassVar
            get_origin(Generic) is Generic
            get_origin(Generic[T]) is Generic
            get_origin(Union[T, int]) is Union
            get_origin(List[Tuple[T, T]][int]) == list
        """
        if is_generic(tp):
            return tp.__origin__
        if tp is Generic:
            return Generic
        return None
