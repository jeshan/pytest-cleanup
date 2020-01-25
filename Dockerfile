FROM python:3.7-alpine

RUN apk add --no-cache tree

WORKDIR /app

RUN pip install pipenv

COPY Pipfile Pipfile.lock ./

RUN pipenv install --system


# temp working directory to install package
WORKDIR /pytest_cleanup

COPY LICENCE* pyproject.toml README.md ./
COPY pytest_cleanup pytest_cleanup


ENV FLIT_ROOT_INSTALL=1
RUN flit install


WORKDIR /app

COPY test test
COPY tests tests

RUN python -m pytest_cleanup # to generate test files

WORKDIR test

RUN cp conftest-pytest-cleanup-runtime.py conftest.py

WORKDIR /app

# run committed tests
RUN pytest --cov-report term-missing --cov=pytest_cleanup -s test/

WORKDIR /app

# run generator that will recreate test cases
RUN python -m tests


RUN cat test/conftest-pytest-cleanup-record.py >> test/conftest.py

ENV PYTESTCLEANUP_LOG_LEVEL=TRACE

# test again with both set of test cases
RUN pytest --cov-report term-missing --cov=pytest_cleanup -s -v test/

WORKDIR /pytest_cleanup
ENTRYPOINT ["flit", "publish"]
ENV FLIT_USERNAME=__token__
