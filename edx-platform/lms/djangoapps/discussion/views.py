"""
Views handling read (GET) requests for the Discussion tab and inline discussions.
"""

from functools import wraps
import logging

from django.contrib.auth.decorators import login_required
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.views.decorators.http import require_GET
import newrelic.agent

from courseware.courses import get_course_with_access
from openedx.core.djangoapps.course_groups.cohorts import (
    is_course_cohorted,
    get_cohort_id,
    get_course_cohorts,
)
from courseware.access import has_access
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore

from django_comment_common.utils import ThreadContext
from django_comment_client.permissions import has_permission, get_team
from django_comment_client.utils import (
    merge_dict,
    extract,
    strip_none,
    add_courseware_context,
    get_group_id_for_comments_service,
    is_commentable_cohorted
)
import django_comment_client.utils as utils
import lms.lib.comment_client as cc

from opaque_keys.edx.keys import CourseKey

THREADS_PER_PAGE = 20
INLINE_THREADS_PER_PAGE = 20
PAGES_NEARBY_DELTA = 2
log = logging.getLogger("edx.discussions")


@newrelic.agent.function_trace()
def make_course_settings(course, user):
    """
    Generate a JSON-serializable model for course settings, which will be used to initialize a
    DiscussionCourseSettings object on the client.
    """

    obj = {
        'is_cohorted': is_course_cohorted(course.id),
        'allow_anonymous': course.allow_anonymous,
        'allow_anonymous_to_peers': course.allow_anonymous_to_peers,
        'cohorts': [{"id": str(g.id), "name": g.name} for g in get_course_cohorts(course)],
        'category_map': utils.get_discussion_category_map(course, user)
    }

    return obj


@newrelic.agent.function_trace()
def get_threads(request, course, user_info, discussion_id=None, per_page=THREADS_PER_PAGE):
    """
    This may raise an appropriate subclass of cc.utils.CommentClientError
    if something goes wrong, or ValueError if the group_id is invalid.

    Arguments:
        request (WSGIRequest): The user request.
        course (CourseDescriptorWithMixins): The course object.
        user_info (dict): The comment client User object as a dict.
        discussion_id (unicode): Optional discussion id/commentable id for context.
        per_page (int): Optional number of threads per page.

    Returns:
        (tuple of list, dict): A tuple of the list of threads and a dict of the
            query parameters used for the search.

    """
    default_query_params = {
        'page': 1,
        'per_page': per_page,
        'sort_key': 'activity',
        'text': '',
        'course_id': unicode(course.id),
        'user_id': request.user.id,
        'context': ThreadContext.COURSE,
        'group_id': get_group_id_for_comments_service(request, course.id, discussion_id),  # may raise ValueError
    }

    # If provided with a discussion id, filter by discussion id in the
    # comments_service.
    if discussion_id is not None:
        default_query_params['commentable_id'] = discussion_id
        # Use the discussion id/commentable id to determine the context we are going to pass through to the backend.
        if get_team(discussion_id) is not None:
            default_query_params['context'] = ThreadContext.STANDALONE

    if not request.GET.get('sort_key'):
        # If the user did not select a sort key, use their last used sort key
        default_query_params['sort_key'] = user_info.get('default_sort_key') or default_query_params['sort_key']

    elif request.GET.get('sort_key') != user_info.get('default_sort_key'):
        # If the user clicked a sort key, update their default sort key
        cc_user = cc.User.from_django_user(request.user)
        cc_user.default_sort_key = request.GET.get('sort_key')
        cc_user.save()

    #there are 2 dimensions to consider when executing a search with respect to group id
    #is user a moderator
    #did the user request a group

    query_params = merge_dict(
        default_query_params,
        strip_none(
            extract(
                request.GET,
                [
                    'page',
                    'sort_key',
                    'text',
                    'commentable_ids',
                    'flagged',
                    'unread',
                    'unanswered',
                ]
            )
        )
    )

    paginated_results = cc.Thread.search(query_params)
    threads = paginated_results.collection

    # If not provided with a discussion id, filter threads by commentable ids
    # which are accessible to the current user.
    if discussion_id is None:
        discussion_category_ids = set(utils.get_discussion_categories_ids(course, request.user))
        threads = [
            thread for thread in threads
            if thread.get('commentable_id') in discussion_category_ids
        ]

    for thread in threads:
        # patch for backward compatibility to comments service
        if 'pinned' not in thread:
            thread['pinned'] = False

    query_params['page'] = paginated_results.page
    query_params['num_pages'] = paginated_results.num_pages
    query_params['corrected_text'] = paginated_results.corrected_text

    return threads, query_params


def use_bulk_ops(view_func):
    """
    Wraps internal request handling inside a modulestore bulk op, significantly
    reducing redundant database calls.  Also converts the course_id parsed from
    the request uri to a CourseKey before passing to the view.
    """
    @wraps(view_func)
    def wrapped_view(request, course_id, *args, **kwargs):  # pylint: disable=missing-docstring
        course_key = CourseKey.from_string(course_id)
        with modulestore().bulk_operations(course_key):
            return view_func(request, course_key, *args, **kwargs)
    return wrapped_view


@login_required
@use_bulk_ops
def inline_discussion(request, course_key, discussion_id):
    """
    Renders JSON for DiscussionModules
    """
    nr_transaction = newrelic.agent.current_transaction()

    course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)
    cc_user = cc.User.from_django_user(request.user)
    user_info = cc_user.to_dict()

    try:
        threads, query_params = get_threads(request, course, user_info, discussion_id, per_page=INLINE_THREADS_PER_PAGE)
    except ValueError:
        return HttpResponseBadRequest("Invalid group_id")

    with newrelic.agent.FunctionTrace(nr_transaction, "get_metadata_for_threads"):
        annotated_content_info = utils.get_metadata_for_threads(course_key, threads, request.user, user_info)
    is_staff = has_permission(request.user, 'openclose_thread', course.id)
    threads = [utils.prepare_content(thread, course_key, is_staff) for thread in threads]
    with newrelic.agent.FunctionTrace(nr_transaction, "add_courseware_context"):
        add_courseware_context(threads, course, request.user)
    return utils.JsonResponse({
        'is_commentable_cohorted': is_commentable_cohorted(course_key, discussion_id),
        'discussion_data': threads,
        'user_info': user_info,
        'annotated_content_info': annotated_content_info,
        'page': query_params['page'],
        'num_pages': query_params['num_pages'],
        'roles': utils.get_role_ids(course_key),
        'course_settings': make_course_settings(course, request.user)
    })


@login_required
@use_bulk_ops
def forum_form_discussion(request, course_key):
    """
    Renders the main Discussion page, potentially filtered by a search query
    """
    nr_transaction = newrelic.agent.current_transaction()

    course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)
    course_settings = make_course_settings(course, request.user)

    user = cc.User.from_django_user(request.user)
    user_info = user.to_dict()

    try:
        unsafethreads, query_params = get_threads(request, course, user_info)   # This might process a search query
        is_staff = has_permission(request.user, 'openclose_thread', course.id)
        threads = [utils.prepare_content(thread, course_key, is_staff) for thread in unsafethreads]
    except cc.utils.CommentClientMaintenanceError:
        log.warning("Forum is in maintenance mode")
        return render_to_response('discussion/maintenance.html', {
            'disable_courseware_js': True,
            'uses_pattern_library': True,
        })
    except ValueError:
        return HttpResponseBadRequest("Invalid group_id")

    with newrelic.agent.FunctionTrace(nr_transaction, "get_metadata_for_threads"):
        annotated_content_info = utils.get_metadata_for_threads(course_key, threads, request.user, user_info)

    with newrelic.agent.FunctionTrace(nr_transaction, "add_courseware_context"):
        add_courseware_context(threads, course, request.user)

    if request.is_ajax():
        return utils.JsonResponse({
            'discussion_data': threads,   # TODO: Standardize on 'discussion_data' vs 'threads'
            'annotated_content_info': annotated_content_info,
            'num_pages': query_params['num_pages'],
            'page': query_params['page'],
            'corrected_text': query_params['corrected_text'],
        })
    else:
        with newrelic.agent.FunctionTrace(nr_transaction, "get_cohort_info"):
            user_cohort_id = get_cohort_id(request.user, course_key)

        context = {
            'csrf': csrf(request)['csrf_token'],
            'course': course,
            #'recent_active_threads': recent_active_threads,
            'staff_access': bool(has_access(request.user, 'staff', course)),
            'threads': threads,
            'thread_pages': query_params['num_pages'],
            'user_info': user_info,
            'can_create_comment': has_permission(request.user, "create_comment", course.id),
            'can_create_subcomment': has_permission(request.user, "create_sub_comment", course.id),
            'can_create_thread': has_permission(request.user, "create_thread", course.id),
            'flag_moderator': bool(
                has_permission(request.user, 'openclose_thread', course.id) or
                has_access(request.user, 'staff', course)
            ),
            'annotated_content_info': annotated_content_info,
            'course_id': course.id.to_deprecated_string(),
            'roles': utils.get_role_ids(course_key),
            'is_moderator': has_permission(request.user, "see_all_cohorts", course_key),
            'cohorts': course_settings["cohorts"],  # still needed to render _thread_list_template
            'user_cohort': user_cohort_id,  # read from container in NewPostView
            'is_course_cohorted': is_course_cohorted(course_key),  # still needed to render _thread_list_template
            'sort_preference': user.default_sort_key,
            'category_map': course_settings["category_map"],
            'course_settings': course_settings,
            'disable_courseware_js': True,
            'uses_pattern_library': True,
        }
        # print "start rendering.."
        return render_to_response('discussion/discussion_board.html', context)


@require_GET
@login_required
@use_bulk_ops
def single_thread(request, course_key, discussion_id, thread_id):
    """
    Renders a response to display a single discussion thread.  This could either be a page refresh
    after navigating to a single thread, a direct link to a single thread, or an AJAX call from the
    discussions UI loading the responses/comments for a single thread.

    Depending on the HTTP headers, we'll adjust our response accordingly.
    """
    nr_transaction = newrelic.agent.current_transaction()

    course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)
    course_settings = make_course_settings(course, request.user)
    cc_user = cc.User.from_django_user(request.user)
    user_info = cc_user.to_dict()
    is_moderator = has_permission(request.user, "see_all_cohorts", course_key)
    is_staff = has_permission(request.user, 'openclose_thread', course.id)

    try:
        thread = cc.Thread.find(thread_id).retrieve(
            with_responses=request.is_ajax(),
            recursive=request.is_ajax(),
            user_id=request.user.id,
            response_skip=request.GET.get("resp_skip"),
            response_limit=request.GET.get("resp_limit")
        )
    except cc.utils.CommentClientRequestError as error:
        if error.status_code == 404:
            raise Http404
        raise

    # Verify that the student has access to this thread if belongs to a course discussion module
    thread_context = getattr(thread, "context", "course")
    if thread_context == "course" and not utils.discussion_category_id_access(course, request.user, discussion_id):
        raise Http404

    # verify that the thread belongs to the requesting student's cohort
    if is_commentable_cohorted(course_key, discussion_id) and not is_moderator:
        user_group_id = get_cohort_id(request.user, course_key)
        if getattr(thread, "group_id", None) is not None and user_group_id != thread.group_id:
            raise Http404

    if request.is_ajax():
        with newrelic.agent.FunctionTrace(nr_transaction, "get_annotated_content_infos"):
            annotated_content_info = utils.get_annotated_content_infos(
                course_key,
                thread,
                request.user,
                user_info=user_info
            )

        content = utils.prepare_content(thread.to_dict(), course_key, is_staff)
        with newrelic.agent.FunctionTrace(nr_transaction, "add_courseware_context"):
            add_courseware_context([content], course, request.user)

        return utils.JsonResponse({
            'content': content,
            'annotated_content_info': annotated_content_info,
        })
    else:
        # Since we're in page render mode, and the discussions UI will request the thread list itself,
        # we need only return the thread information for this one.
        threads = [thread.to_dict()]

        with newrelic.agent.FunctionTrace(nr_transaction, "add_courseware_context"):
            add_courseware_context(threads, course, request.user)

        for thread in threads:
            # patch for backward compatibility with comments service
            if "pinned" not in thread:
                thread["pinned"] = False

        threads = [utils.prepare_content(thread, course_key, is_staff) for thread in threads]

        with newrelic.agent.FunctionTrace(nr_transaction, "get_metadata_for_threads"):
            annotated_content_info = utils.get_metadata_for_threads(course_key, threads, request.user, user_info)

        with newrelic.agent.FunctionTrace(nr_transaction, "get_cohort_info"):
            user_cohort = get_cohort_id(request.user, course_key)

        context = {
            'discussion_id': discussion_id,
            'csrf': csrf(request)['csrf_token'],
            'init': '',   # TODO: What is this?
            'user_info': user_info,
            'can_create_comment': has_permission(request.user, "create_comment", course.id),
            'can_create_subcomment': has_permission(request.user, "create_sub_comment", course.id),
            'can_create_thread': has_permission(request.user, "create_thread", course.id),
            'annotated_content_info': annotated_content_info,
            'course': course,
            #'recent_active_threads': recent_active_threads,
            'course_id': course.id.to_deprecated_string(),   # TODO: Why pass both course and course.id to template?
            'thread_id': thread_id,
            'threads': threads,
            'roles': utils.get_role_ids(course_key),
            'is_moderator': is_moderator,
            'thread_pages': 1,
            'is_course_cohorted': is_course_cohorted(course_key),
            'flag_moderator': bool(
                has_permission(request.user, 'openclose_thread', course.id) or
                has_access(request.user, 'staff', course)
            ),
            'cohorts': course_settings["cohorts"],
            'user_cohort': user_cohort,
            'sort_preference': cc_user.default_sort_key,
            'category_map': course_settings["category_map"],
            'course_settings': course_settings,
            'disable_courseware_js': True,
            'uses_pattern_library': True,
        }
        return render_to_response('discussion/discussion_board.html', context)


@require_GET
@login_required
@use_bulk_ops
def user_profile(request, course_key, user_id):
    """
    Renders a response to display the user profile page (shown after clicking
    on a post author's username).
    """

    nr_transaction = newrelic.agent.current_transaction()

    user = cc.User.from_django_user(request.user)
    user_info = user.to_dict()
    course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)
    course_settings = make_course_settings(course, request.user)

    try:
        # If user is not enrolled in the course, do not proceed.
        django_user = User.objects.get(id=user_id)
        if not CourseEnrollment.is_enrolled(django_user, course.id):
            raise Http404

        query_params = {
            'page': request.GET.get('page', 1),
            'per_page': THREADS_PER_PAGE,   # more than threads_per_page to show more activities
        }

        try:
            group_id = get_group_id_for_comments_service(request, course_key)
        except ValueError:
            return HttpResponseBadRequest("Invalid group_id")
        if group_id is not None:
            query_params['group_id'] = group_id
            profiled_user = cc.User(id=user_id, course_id=course_key, group_id=group_id)
        else:
            profiled_user = cc.User(id=user_id, course_id=course_key)

        threads, page, num_pages = profiled_user.active_threads(query_params)
        query_params['page'] = page
        query_params['num_pages'] = num_pages
        user_info = cc.User.from_django_user(request.user).to_dict()

        with newrelic.agent.FunctionTrace(nr_transaction, "get_metadata_for_threads"):
            annotated_content_info = utils.get_metadata_for_threads(course_key, threads, request.user, user_info)

        is_staff = has_permission(request.user, 'openclose_thread', course.id)
        threads = [utils.prepare_content(thread, course_key, is_staff) for thread in threads]
        with newrelic.agent.FunctionTrace(nr_transaction, "add_courseware_context"):
            add_courseware_context(threads, course, request.user)
        if request.is_ajax():
            return utils.JsonResponse({
                'discussion_data': threads,
                'page': query_params['page'],
                'num_pages': query_params['num_pages'],
                'annotated_content_info': annotated_content_info,
            })
        else:
            user_roles = django_user.roles.filter(
                course_id=course.id
            ).order_by("name").values_list("name", flat=True).distinct()

            with newrelic.agent.FunctionTrace(nr_transaction, "get_cohort_info"):
                user_cohort_id = get_cohort_id(request.user, course_key)

            context = {
                'course': course,
                'user': request.user,
                'django_user': django_user,
                'django_user_roles': user_roles,
                'profiled_user': profiled_user.to_dict(),
                'threads': threads,
                'user_info': user_info,
                'roles': utils.get_role_ids(course_key),
                'can_create_comment': has_permission(request.user, "create_comment", course.id),
                'can_create_subcomment': has_permission(request.user, "create_sub_comment", course.id),
                'can_create_thread': has_permission(request.user, "create_thread", course.id),
                'flag_moderator': bool(
                    has_permission(request.user, 'openclose_thread', course.id) or
                    has_access(request.user, 'staff', course)
                ),
                'user_cohort': user_cohort_id,
                'annotated_content_info': annotated_content_info,
                'page': query_params['page'],
                'num_pages': query_params['num_pages'],
                'sort_preference': user.default_sort_key,
                'course_settings': course_settings,
                'learner_profile_page_url': reverse('learner_profile', kwargs={'username': django_user.username}),
                'disable_courseware_js': True,
                'uses_pattern_library': True,
            }

            return render_to_response('discussion/discussion_profile_page.html', context)
    except User.DoesNotExist:
        raise Http404


@login_required
@use_bulk_ops
def followed_threads(request, course_key, user_id):
    """
    Ajax-only endpoint retrieving the threads followed by a specific user.
    """

    nr_transaction = newrelic.agent.current_transaction()

    course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)
    try:
        profiled_user = cc.User(id=user_id, course_id=course_key)

        default_query_params = {
            'page': 1,
            'per_page': THREADS_PER_PAGE,   # more than threads_per_page to show more activities
            'sort_key': 'date',
        }

        query_params = merge_dict(
            default_query_params,
            strip_none(
                extract(
                    request.GET,
                    [
                        'page',
                        'sort_key',
                        'flagged',
                        'unread',
                        'unanswered',
                    ]
                )
            )
        )

        try:
            group_id = get_group_id_for_comments_service(request, course_key)
        except ValueError:
            return HttpResponseBadRequest("Invalid group_id")
        if group_id is not None:
            query_params['group_id'] = group_id

        paginated_results = profiled_user.subscribed_threads(query_params)
        print "\n \n \n paginated results \n \n \n "
        print paginated_results
        query_params['page'] = paginated_results.page
        query_params['num_pages'] = paginated_results.num_pages
        user_info = cc.User.from_django_user(request.user).to_dict()

        with newrelic.agent.FunctionTrace(nr_transaction, "get_metadata_for_threads"):
            annotated_content_info = utils.get_metadata_for_threads(
                course_key,
                paginated_results.collection,
                request.user, user_info
            )
        if request.is_ajax():
            is_staff = has_permission(request.user, 'openclose_thread', course.id)
            return utils.JsonResponse({
                'annotated_content_info': annotated_content_info,
                'discussion_data': [
                    utils.prepare_content(thread, course_key, is_staff) for thread in paginated_results.collection
                ],
                'page': query_params['page'],
                'num_pages': query_params['num_pages'],
            })
        #TODO remove non-AJAX support, it does not appear to be used and does not appear to work.
        else:
            context = {
                'course': course,
                'user': request.user,
                'django_user': User.objects.get(id=user_id),
                'profiled_user': profiled_user.to_dict(),
                'threads': paginated_results.collection,
                'user_info': user_info,
                'annotated_content_info': annotated_content_info,
                #                'content': content,
            }

            return render_to_response('discussion/user_profile.html', context)
    except User.DoesNotExist:
        raise Http404
