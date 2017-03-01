"""
Utilities for grades related tests
"""
from contextlib import contextmanager
from mock import patch
from courseware.module_render import get_module
from courseware.model_data import FieldDataCache
from xmodule.graders import ProblemScore


@contextmanager
def mock_passing_grade(grade_pass='Pass', percent=0.75, ):
    """
    Mock the grading function to always return a passing grade.
    """
    with patch('lms.djangoapps.grades.new.course_grade.CourseGrade._compute_letter_grade') as mock_letter_grade:
        with patch('lms.djangoapps.grades.new.course_grade.CourseGrade._calc_percent') as mock_percent_grade:
            mock_letter_grade.return_value = grade_pass
            mock_percent_grade.return_value = percent
            yield


@contextmanager
def mock_get_score(earned=0, possible=1):
    """
    Mocks the get_score function to return a valid grade.
    """
    with patch('lms.djangoapps.grades.new.subsection_grade.get_score') as mock_score:
        mock_score.return_value = ProblemScore(
            raw_earned=earned,
            raw_possible=possible,
            weighted_earned=earned,
            weighted_possible=possible,
            weight=1,
            graded=True,
            attempted=True,
        )
        yield mock_score


@contextmanager
def mock_get_submissions_score(earned=0, possible=1, attempted=True):
    """
    Mocks the _get_submissions_score function to return the specified values
    """
    with patch('lms.djangoapps.grades.scores._get_score_from_submissions') as mock_score:
        mock_score.return_value = (earned, possible, earned, possible, attempted)
        yield mock_score


def answer_problem(course, request, problem, score=1, max_value=1):
    """
    Records a correct answer for the given problem.

    Arguments:
        course (Course): Course object, the course the required problem is in
        request (Request): request Object
        problem (xblock): xblock object, the problem to be answered
    """

    user = request.user
    grade_dict = {'value': score, 'max_value': max_value, 'user_id': user.id}
    field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
        course.id,
        user,
        course,
        depth=2
    )
    # pylint: disable=protected-access
    module = get_module(
        user,
        request,
        problem.scope_ids.usage_id,
        field_data_cache,
    )._xmodule
    module.system.publish(problem, 'grade', grade_dict)
