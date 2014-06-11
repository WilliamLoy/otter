# coding: utf-8

"""Functional programming helpers."""


def conj(d, new_fields):
    """Conj[oin] two dicts without side-effects."""
    if d is None:
        d = {}
    if new_fields is None:
        new_fields = {}
    new_d = d.copy()
    new_d.update(new_fields)
    return new_d


def wrap(f, g):
    """
    'The wrapper combinator'

    Given f, any function, and g, a function which accepts a callable as its
    first argument, return a function:

        λ(*args, **kwargs): g(f, *args, **kwargs)

    This allows g to "wrap" f, so that g is responsible for calling f. f must expect a
    callable as its first argument, of course.

    This is basically a way to do dependency injection -- if a function g
    wants to call f, instead of just referring to f directly, it can accept
    it as a parameter.
    """
    return lambda *args, **kwargs: g(f, *args, **kwargs)


def wrappers(*stuff):
    """
    Combine a number of functions with the wrapper combinator.

    The first function is the 'innermost', and the last is the outermost.
    All functions after the first should take a callable as their first argument.
    """
    return reduce(wrap, stuff)
