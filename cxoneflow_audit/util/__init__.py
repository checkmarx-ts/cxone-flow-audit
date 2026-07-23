import re, requests


class NameMatcher:

    @staticmethod
    def create_as_skip(regex: str):
        inst = NameMatcher()
        inst.__regex = re.compile(regex)
        inst.__invert = True
        return inst

    @staticmethod
    def create_as_match(regex: str):
        inst = NameMatcher()
        inst.__regex = re.compile(regex)
        inst.__invert = False
        return inst

    def matches(self, test_value: str) -> bool:
        result = self.__regex.search(test_value)

        return not bool(result) if self.__invert else bool(result)


class ScmException(Exception):

    def __init__(self, response: requests.Response):
        Exception.__init__(
            self,
            f"{response.request.url} response: {response.status_code}: {response.text}",
        )
        self.__response = response

    @property
    def response(self) -> requests.Response:
        return self.__response


class NotFoundException(Exception): ...
