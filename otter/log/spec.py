"""
Format logs based on specification
"""
import json
import math

from toolz.dicttoolz import assoc, keyfilter
from toolz.functoolz import compose, curry

from twisted.python.failure import Failure


_json_len = compose(len, json.dumps)


def split_execute_convergence(event, max_length=50000):
    """
    Try to split execute-convergence event out into multiple events if there
    are too many CLB nodes, too many servers, or too many steps.

    The problem is mainly the servers, since they take up the most space.

    Experimentally determined that probably logs cut off at around 75k,
    characters - we're going to limit it to 50k.

    :param dict event: The 'execute-convergence' type event dictionary to split
    :param int max_length: The maximum length of the entire JSON-formatted
        dictionary.

    :return: `list` of `tuple` of (`dict`, `str`).  The `dict`s in the tuple
        represents the spit up event dicts, and the `str` the format string
        for each.  If the event does not need to be split, the list will only
        have one tuple.
    """
    message = "Executing convergence"
    if _json_len(event) <= max_length:
        return [(event, message)]

    events = [(event, message)]
    large_things = sorted(('servers', 'lb_nodes'),
                          key=compose(_json_len, event.get),
                          reverse=True)

    # simplified event which serves as a base for the split out events
    base_event = keyfilter(
        lambda k: k not in ('desired', 'servers', 'lb_nodes', 'steps'),
        event)

    for thing in large_things:
        split_up_events = split(
            curry(assoc, base_event, thing), event[thing], max_length,
            _json_len)
        events.extend([(e, message) for e in split_up_events])
        del event[thing]
        if _json_len(event) <= max_length:
            break

    return events


# mapping from msg type -> message
msg_types = {
    # Keep these in alphabetical order so merges can be deterministic
    # These can be callables as well with the following type:
    # event -> [(event, format_str)]
    "add-server-clb": ("Adding {server_id} with IP address {ip_address} "
                       "to CLB {clb_id}"),
    "converge-all-groups": "Attempting to converge all dirty groups",
    "converge-all-groups-error": "Error while converging all groups",
    "converge-divergent-flag-disappeared":
        "Divergent flag {znode} disappeared when trying to start convergence. "
        "This should be harmless.",
    "converge-fatal-error": (
        "Fatal error while converging group {scaling_group_id}."),
    "converge-non-fatal-error": (
        "Non-fatal error while converging group {scaling_group_id}"),
    "delete-server": "Deleting {server_id} server",
    "execute-convergence": split_execute_convergence,
    "execute-convergence-results": (
        "Got result of {worst_status} after executing convergence"),
    "launch-servers": "Launching {num_servers} servers",
    "mark-clean-failure": "Failed to mark group {scaling_group_id} clean",
    "mark-clean-not-found": (
        "Dirty flag of group {scaling_group_id} not found when deleting"),
    "mark-clean-skipped": (
        "Not marking group {scaling_group_id} clean because another "
        "convergence was requested."),
    "mark-clean-success": "Marked group {scaling_group_id} clean",
    "mark-dirty-success": "Marked group {scaling_group_id} dirty",
    "mark-dirty-failure": "Failed to mark group {scaling_group_id} dirty",
    "remove-server-clb": ("Removing server {server_id} with IP address "
                          "{ip_address} from CLB {clb_id}"),
    "request-create-server": (
        "Request to create a server succeeded with response: {response_body}"),
    "request-list-servers-details": ("Request to list servers succeeded"),

    # CF-published log messages
    "cf-add-failure": "Failed to add event to cloud feeds",
    "cf-unsuitable-message": (
        "Tried to add unsuitable message in cloud feeds: "
        "{unsuitable_message}"),
    "convergence-create-servers":
        "Creating {num_servers} with config {server_config}",
    "convergence-delete-servers": "Deleting {servers}",
    "convergence-add-clb-nodes":
        "Adding IPs to CLB {lb_id}: {addresses}",
    "convergence-remove-clb-nodes":
        "Removing nodes from CLB {lb_id}: {nodes}",
    "convergence-change-clb-nodes":
        "Changing nodes on CLB {lb_id}: nodes={nodes}, type={type}, "
        "condition={condition}, weight={weight}",
    "convergence-add-rcv3-nodes":
        "Adding servers to RCv3 LB {lb_id}: {servers}",
    "convergence-remove-rcv3-nodes":
        "Removing servers from RCv3 LB {lb_id}: {servers}",
    "group-status-active": "Group's status is changed to ACTIVE",
    "group-status-error":
        "Group's status is changed to ERROR. Reasons: {reasons}",
}


def halve(l):
    """
    Split a sequence in half, biased to the left.

    :param list l: The sequence to split
    :return: a `tuple` containing both halves of the sequence.
    """
    half_index = int(math.ceil(len(l) / 2.0))
    return (l[:half_index], l[half_index:])


def split(render, elements, max_len, calculate_len=len):
    """
    Render some elements of a list, where the length (as determined by
    ``calculate_len``) of each rendered object is no longer than ``max_len``.

    Messages longer than the max that are rendered from individual elements
    will still be returned, so ``max_len`` mustn't be assumed to be a hard
    constraint.

    :param callable render: A callable which takes a list of elements, and
        produces an object string the list of elements be rendered to.
    :param list elements: A list of elements that should be potentially split.
    :param int max_len: Maximum length of the rendered object, as calculated
        by ``calculate_len``.
    :param callable calculate_len: A callable that takes the rendered object
        and calculates the length.

    :return: a `list` of `list`s of elements, each of which, when rendered
        and measured with the provided callables, should probably be less than
        ``max_len``.
    """
    m = render(elements)
    if len(elements) > 1 and calculate_len(m) > max_len:
        left, right = halve(elements)
        return (split(render, left, max_len, calculate_len) +
                split(render, right, max_len, calculate_len))
    else:
        return [m]


def error_event(event, failure, why):
    """
    Convert event to error with failure and why
    """
    return {"isError": True, "failure": failure,
            "why": why, "original_event": event, "message": ()}


class MsgTypeNotFound(Exception):
    """
    Raised when msg_type is not found
    """


def try_msg_types(event, specs, tries):
    """
    Try series of msg_types
    """
    for msg_type in tries:
        if msg_type in specs:
            formatter = specs[msg_type]
            if callable(formatter):
                events = formatter(event)
            else:
                events = [(event, formatter)]

            return events, msg_type
    raise MsgTypeNotFound(msg_type)


def get_validated_event(event, specs=msg_types):
    """
    Validate event's message as per msg_types and error details as
    per error_fields

    :return: A list of validated events.
    :raises: `ValueError` or `TypeError` if `event_dict` is not valid
    """
    try:
        # message is tuple of strings
        message = ''.join(event.get("message", []))
        error = event.get('isError', False)
        # Is this message speced?
        if error:
            validate_error(event)

        events_and_messages, msg_type = try_msg_types(
            event, specs,
            [event.get("why", None), message] if error else [message])

        # TODO: Validate non-primitive fields
        for i, (e, m) in enumerate(events_and_messages):
            e["otter_msg_type"] = msg_type
            if error:
                e['why'] = m

            if not error or message:
                e['message'] = (m,)

            if len(events_and_messages) > 1:
                e['split_message'] = "{0} of {1}".format(
                    i + 1, len(events_and_messages))

        return [e for e, _ in events_and_messages]
    except MsgTypeNotFound:
        return [event]


def SpecificationObserverWrapper(observer,
                                 get_validated_event=get_validated_event):
    """
    Return observer that validates messages based on specification
    and delegates to given observer.

    Messages are expected to be logged like

    >>> log.msg("launch-servers", num_servers=2)

    where "launch-servers" is message type that will be expanded based on
    entry in msg_types. For errors, the string should be provided in
    "why" field like:

    >>> log.err(f, "execute-convergence-error")
    """
    def validating_observer(event_dict):
        try:
            speced_events = get_validated_event(event_dict)
        except (ValueError, TypeError):
            speced_events = [error_event(
                event_dict, Failure(), "Error validating event")]
        for event in speced_events:
            observer(event)

    return validating_observer


def validate_error(event):
    """
    Validate failure in the event
    """
    # TODO: Left blank to fill implementation using JSON schema
