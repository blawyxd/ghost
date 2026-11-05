"""Editor-backed coding exercises executed in a timed child process.

Execution is isolated from Ghost's process and given a temporary working
directory, but it is not a security sandbox. Malicious code can still access
the user's files, network, or other system resources.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    instructions: str
    starter: str
    tests: tuple[tuple[object, object], ...]
    hints: tuple[str, ...]
    solution: str
    difficulty: str = "beginner"
    function: str = "solve"
    mode: str = "function"


EXERCISES: dict[str, Exercise] = {
    "hello_program": Exercise(
        "hello_program", "Write your first interactive program",
        "Ask for a person's name with the prompt 'Name: ' and print 'Hello, NAME' using print(). Write a complete program, not a function.",
        "# Ask for a name.\n\n# Print a greeting.\n",
        (("Ada\n", "Name: Hello, Ada\n"), ("Grace Hopper\n", "Name: Hello, Grace Hopper\n"), ("Linus\n", "Name: Hello, Linus\n")),
        ("Use input('Name: ') to read text.", "Pass the returned name to print() after the text 'Hello,'."),
        "name = input('Name: ')\nprint('Hello,', name)\n",
        mode="script",
    ),
    "two_greetings": Exercise(
        "two_greetings", "Greet two people",
        "Read two names with the prompt 'Name: ' each time and print one greeting for each person. Write a complete program using print() and variables.",
        "# Read two names.\n\n# Print a greeting for each name.\n",
        (("Ada\nGrace\n", "Name: Name: Hello, Ada\nHello, Grace\n"),
         ("Linus\nMargaret\n", "Name: Name: Hello, Linus\nHello, Margaret\n")),
        ("Call input('Name: ') twice and store each result.", "Use one print() call per greeting; print('Hello,', name) includes the separating space."),
        "first_name = input('Name: ')\nsecond_name = input('Name: ')\nprint('Hello,', first_name)\nprint('Hello,', second_name)\n",
        mode="script",
    ),
    "profile_display": Exercise(
        "profile_display", "Store and display profile values",
        "Read a name and age using the prompts 'Name: ' and 'Age: '. Store each answer in a variable, then print them as 'NAME is AGE'. The age can remain text.",
        "# Read a name and an age into variables.\n\n# Display both values.\n",
        (("Ada\n36\n", "Name: Age: Ada is 36\n"), ("Grace\n85\n", "Name: Age: Grace is 85\n")),
        ("Assign each input() result to a clearly named variable.", "print(name, 'is', age) inserts spaces between the three values."),
        "name = input('Name: ')\nage = input('Age: ')\nprint(name, 'is', age)\n",
        mode="script",
    ),
    "calculate_expression": Exercise(
        "calculate_expression", "Calculate with user-provided numbers",
        "Read two whole numbers using the prompts 'First: ' and 'Second: '. Convert both answers with int(), then print their sum and product on separate lines.",
        "# Read and convert two numbers.\n\n# Print their sum and product.\n",
        (("3\n4\n", "First: Second: 7\n12\n"), ("-2\n5\n", "First: Second: 3\n-10\n"), ("0\n9\n", "First: Second: 9\n0\n")),
        ("input() returns text, so convert each answer with int().", "Use + for the sum and * for the product; print each result separately."),
        "first = int(input('First: '))\nsecond = int(input('Second: '))\nprint(first + second)\nprint(first * second)\n",
        mode="script",
    ),
    "unit_converter": Exercise(
        "unit_converter", "Convert kilometres to miles",
        "Ask for a distance in kilometres using the prompt 'Kilometres: '. Convert it to miles using 1 mile = 1.60934 kilometres, then print one decimal place as 'Miles: N.N'.",
        "# Read the distance, calculate miles, and display one decimal place.\n",
        (("1.60934\n", "Kilometres: Miles: 1.0\n"), ("0\n", "Kilometres: Miles: 0.0\n"), ("16.0934\n", "Kilometres: Miles: 10.0\n")),
        ("Convert the input with float().", "Divide kilometres by 1.60934 and format the answer with :.1f in an f-string."),
        "kilometres = float(input('Kilometres: '))\nmiles = kilometres / 1.60934\nprint(f'Miles: {miles:.1f}')\n",
        mode="script",
    ),
    "score_branching": Exercise(
        "score_branching", "Choose a branch from a score",
        "Read an integer score with the prompt 'Score: '. Print 'excellent' for 90 or more, 'pass' for 60 through 89, and 'retry' below 60.",
        "# Read a score, choose a branch, and print its label.\n",
        (("90\n", "Score: excellent\n"), ("60\n", "Score: pass\n"), ("59\n", "Score: retry\n"), ("100\n", "Score: excellent\n")),
        ("Convert the input to int() before comparing it.", "Check >= 90 first, then >= 60 with elif, and use else for the remaining scores."),
        "score = int(input('Score: '))\nif score >= 90:\n    result = 'excellent'\nelif score >= 60:\n    result = 'pass'\nelse:\n    result = 'retry'\nprint(result)\n",
        mode="script",
    ),
    "loop_sum": Exercise(
        "loop_sum", "Add a sequence with a loop",
        "Read a whole number with the prompt 'Limit: '. Use a for loop to add the integers from 1 through that limit, then print the total. A limit of 0 produces 0.",
        "# Read the limit, add the sequence with a loop, and print the total.\n",
        (("3\n", "Limit: 6\n"), ("1\n", "Limit: 1\n"), ("0\n", "Limit: 0\n"), ("5\n", "Limit: 15\n")),
        ("Start total at zero.", "Use range(1, limit + 1) so the limit is included; when limit is zero, the loop is empty."),
        "limit = int(input('Limit: '))\ntotal = 0\nfor number in range(1, limit + 1):\n    total += number\nprint(total)\n",
        mode="script",
    ),
    "greeting": Exercise(
        "greeting", "Personal greeting",
        "Complete greet(name) so it returns 'Hello, NAME!' using the name passed in.",
        "def greet(name):\n    # Return a personalised greeting.\n    pass\n",
        ((("Ada",), "Hello, Ada!"), (("Grace Hopper",), "Hello, Grace Hopper!"), (("",), "Hello, !")),
        ("Return a string; do not print it.", "Use an f-string: f'Hello, {name}!'"),
        "def greet(name):\n    return f'Hello, {name}!'\n", function="greet",
    ),
    "profile": Exercise(
        "profile", "Build a profile summary",
        "Implement describe(name, age) returning 'NAME is AGE years old.' as a string.",
        "def describe(name, age):\n    # Return the formatted description.\n    pass\n",
        ((("Ada", 36), "Ada is 36 years old."), (("Linus", 55), "Linus is 55 years old.")),
        ("The function should return one string.", "An f-string can format text and numeric values together."),
        "def describe(name, age):\n    return f'{name} is {age} years old.'\n", function="describe",
    ),
    "temperature": Exercise(
        "temperature", "Convert Celsius to Fahrenheit",
        "Implement to_fahrenheit(celsius). Use F = C * 9 / 5 + 32 and return a number.",
        "def to_fahrenheit(celsius):\n    # Convert and return the temperature.\n    pass\n",
        (((0,), 32), ((100,), 212), ((-40,), -40)),
        ("Multiply Celsius by 9/5, then add 32.", "Keep the arithmetic in a function and return its result."),
        "def to_fahrenheit(celsius):\n    return celsius * 9 / 5 + 32\n", function="to_fahrenheit",
    ),
    "echo": Exercise(
        "echo", "Create a labelled message",
        "Implement make_message(name, message) returning '[NAME] MESSAGE' with the supplied values.",
        "def make_message(name, message):\n    # Return the labelled message.\n    pass\n",
        ((("Ari", "Ready"), "[Ari] Ready"), (("", "Hello"), "[] Hello")),
        ("Build one string from both arguments.", "The expected shape is an opening bracket, name, closing bracket, a space, then message."),
        "def make_message(name, message):\n    return f'[{name}] {message}'\n", function="make_message",
    ),
    "interactive_greeting": Exercise(
        "interactive_greeting", "Greet a person at the terminal",
        "Write a complete program that asks for a name with input() and prints 'Hello, NAME!' on the next line.",
        "# Read a name from input().\n\n# Print a greeting using the name.\n",
        (("Ada\n", "Name: Hello, Ada!\n"), ("Grace Hopper\n", "Name: Hello, Grace Hopper!\n")),
        ("Call input() with the prompt 'Name: '.", "Store the returned string, then pass an f-string to print()."),
        "name = input('Name: ')\nprint(f'Hello, {name}!')\n",
        difficulty="beginner", mode="script",
    ),
    "classify": Exercise(
        "classify", "Classify a score",
        "Implement grade(score): return 'excellent' for 90+, 'pass' for 60–89, otherwise 'retry'.",
        "def grade(score):\n    # Return excellent, pass, or retry.\n    pass\n",
        (((100,), "excellent"), ((90,), "excellent"), ((60,), "pass"), ((59,), "retry")),
        ("Check the highest threshold first.", "Use if / elif / else and return the matching label."),
        "def grade(score):\n    if score >= 90:\n        return 'excellent'\n    elif score >= 60:\n        return 'pass'\n    return 'retry'\n", function="grade",
    ),
    "sum_numbers": Exercise(
        "sum_numbers", "Sum a sequence",
        "Implement sum_numbers(values) that returns the total of all numbers; an empty sequence totals zero.",
        "def sum_numbers(values):\n    # Add each value and return the total.\n    pass\n",
        ((([1, 2, 3],), 6), (([],), 0), (([-2, 5],), 3)),
        ("Start with a total of zero.", "Loop over values and add each one to the total."),
        "def sum_numbers(values):\n    total = 0\n    for value in values:\n        total += value\n    return total\n", function="sum_numbers",
    ),
    "is_even": Exercise(
        "is_even", "Check whether a number is even",
        "Implement is_even(number) returning True for even integers and False otherwise.",
        "def is_even(number):\n    # Return a Boolean.\n    pass\n",
        (((2,), True), ((7,), False), ((0,), True), ((-4,), True)),
        ("The remainder operator is %.", "A number is even when number % 2 equals zero."),
        "def is_even(number):\n    return number % 2 == 0\n", function="is_even",
    ),
    "summarise_numbers": Exercise(
        "summarise_numbers", "Summarise a list of numbers",
        "Return a dictionary with keys 'count', 'total', and 'average'. Empty input has average 0.",
        "def summarise_numbers(values):\n    # Return count, total, and average.\n    pass\n",
        ((([2, 4, 6],), {"count": 3, "total": 12, "average": 4}), (([],), {"count": 0, "total": 0, "average": 0})),
        ("Compute the count and total first.", "Only divide by the count when it is nonzero."),
        "def summarise_numbers(values):\n    count = len(values)\n    total = sum(values)\n    average = total / count if count else 0\n    return {'count': count, 'total': total, 'average': average}\n", function="summarise_numbers",
    ),
    "count_words": Exercise(
        "count_words", "Count words in text",
        "Implement count_words(text) returning the number of whitespace-separated words.",
        "def count_words(text):\n    # Return the word count.\n    pass\n",
        ((("one two three",), 3), (("  extra   spaces ",), 2), (("",), 0)),
        ("Whitespace includes spaces and line breaks.", "Calling split() without a separator handles repeated whitespace."),
        "def count_words(text):\n    return len(text.split())\n", function="count_words",
    ),
    "safe_divide": Exercise(
        "safe_divide", "Handle division by zero",
        "Implement safe_divide(a, b): return a / b, or None when b is zero.",
        "def safe_divide(a, b):\n    # Return the quotient or None.\n    pass\n",
        (((8, 2), 4), ((5, 2), 2.5), ((3, 0), None)),
        ("Check the divisor before dividing.", "Return None from the zero case, then return a / b."),
        "def safe_divide(a, b):\n    if b == 0:\n        return None\n    return a / b\n", function="safe_divide",
    ),
    "line_count": Exercise(
        "line_count", "Count lines",
        "Implement line_count(text) counting newline-separated lines. Empty text has zero lines; a final newline adds no extra line.",
        "def line_count(text):\n    # Return the number of lines.\n    pass\n",
        ((("",), 0), (("one",), 1), (("one\ntwo",), 2), (("one\n",), 1)),
        ("Handle empty text as a special case.", "splitlines() returns lines without treating a final newline as an extra line."),
        "def line_count(text):\n    return len(text.splitlines())\n", function="line_count",
    ),
    "file_summary": Exercise(
        "file_summary", "Summarise a text file",
        "Write a program that asks for a filename, reads its UTF-8 text, and prints the number of lines. If the file is missing, print 'File not found' instead of crashing.",
        "from pathlib import Path\n\n# Ask for a filename, then read and summarise it.\n",
        (("notes.txt\n", "File: 2 lines\n", {"notes.txt": "alpha\nbeta\n"}),
         ("empty.txt\n", "File: 0 lines\n", {"empty.txt": ""}),
         ("notes.txt\n", "File: File not found\n", {}),
         ("missing.txt\n", "File: File not found\n", {})),
        ("Path(filename).read_text reads the file as text.", "Put the read inside try and catch FileNotFoundError; use splitlines() to count lines."),
        "from pathlib import Path\n\nfilename = input('File: ')\ntry:\n    text = Path(filename).read_text(encoding='utf-8')\nexcept FileNotFoundError:\n    print('File not found')\nelse:\n    print(f'{len(text.splitlines())} lines')\n",
        difficulty="beginner", mode="script",
    ),
    "normalise_name": Exercise(
        "normalise_name", "Normalise a name",
        "Implement normalise_name(name) by trimming surrounding whitespace and title-casing the result.",
        "def normalise_name(name):\n    pass\n",
        ((("  ada lovelace ",), "Ada Lovelace"), (("GRACE HOPPER",), "Grace Hopper")),
        ("Strings have strip() and title() methods.", "Apply strip() before title()."),
        "def normalise_name(name):\n    return name.strip().title()\n", function="normalise_name",
    ),
    "cart_total": Exercise(
        "cart_total", "Calculate a cart total",
        "Implement cart_total(items) where each item is a dictionary with a numeric 'price' key.",
        "def cart_total(items):\n    pass\n",
        ((([{"price": 3}, {"price": 4.5}],), 7.5), (([],), 0)),
        ("Each dictionary stores one price.", "Add the prices across every item."),
        "def cart_total(items):\n    return sum(item['price'] for item in items)\n", function="cart_total",
    ),
    "running_total": Exercise(
        "running_total", "Build running totals",
        "Implement running_total(values) returning a list containing the cumulative total after each value.",
        "def running_total(values):\n    pass\n",
        ((([2, 3, 1],), [2, 5, 6]), (([],), []), (((-1, 4),), [-1, 3])),
        ("Keep a total and a result list.", "Update the total, then append it for each value."),
        "def running_total(values):\n    total = 0\n    result = []\n    for value in values:\n        total += value\n        result.append(total)\n    return result\n", function="running_total",
    ),
    "apply_discount": Exercise(
        "apply_discount", "Apply a percentage discount",
        "Implement apply_discount(total, percent) returning the total after a percentage discount.",
        "def apply_discount(total, percent):\n    pass\n",
        (((100, 10), 90), ((80, 25), 60), ((50, 0), 50)),
        ("A 10 percent discount keeps 90 percent of the price.", "Multiply by (100 - percent) / 100."),
        "def apply_discount(total, percent):\n    return total * (100 - percent) / 100\n", function="apply_discount",
    ),
    "find_user": Exercise(
        "find_user", "Find a user by ID",
        "Implement find_user(users, user_id) returning the matching name, or None if absent.",
        "def find_user(users, user_id):\n    pass\n",
        ((({"1": "Ada", "2": "Grace"}, "2"), "Grace"), (({"1": "Ada"}, "9"), None)),
        ("The IDs are dictionary keys.", "Use dict.get() to return None for an absent key."),
        "def find_user(users, user_id):\n    return users.get(user_id)\n", function="find_user",
    ),
    "normalise_dependencies": Exercise(
        "normalise_dependencies", "Normalise dependency names",
        "Implement normalise_dependencies(names) returning sorted, lowercase unique names.",
        "def normalise_dependencies(names):\n    pass\n",
        (((["Rich", "typer", "rich"],), ["rich", "typer"]), (([],), [])),
        ("Lowercase each name and remove duplicates with a set.", "Sort the unique result before returning it."),
        "def normalise_dependencies(names):\n    return sorted({name.lower() for name in names})\n", function="normalise_dependencies",
    ),
    "parse_record": Exercise(
        "parse_record", "Parse a JSON record",
        "Implement parse_record(text) returning the Python value decoded from JSON text.",
        "def parse_record(text):\n    pass\n",
        ((("{\"name\": \"Ada\"}",), {"name": "Ada"}), (("[1, 2]",), [1, 2])),
        ("The json module parses JSON strings.", "Call json.loads(text) after importing json."),
        "import json\n\ndef parse_record(text):\n    return json.loads(text)\n", function="parse_record",
    ),
    "api_client": Exercise(
        "api_client", "Read a JSON HTTP response",
        "Write a complete program that asks for a URL, makes a timed HTTP request, parses its JSON response, and prints its 'name' value. Handle HTTP errors and invalid JSON with clear messages. Tests use mocked responses and make no network connection.",
        "import json\nfrom urllib.request import urlopen\n\nurl = input('URL: ')\n# Request the URL with a timeout and decode its JSON response.\n",
        (("{\"name\": \"Ada\"}", 200, "URL: Ada\n"),
         ("{\"error\": \"missing\"}", 404, "URL: Request failed: HTTP 404\n"),
         ("not json", 200, "URL: Invalid JSON response\n")),
        ("Use urllib.request.urlopen(url, timeout=2) inside a with block.", "Catch HTTPError before URLError, and catch json.JSONDecodeError separately from network failures."),
        "import json\nfrom urllib.error import HTTPError, URLError\nfrom urllib.request import urlopen\n\nurl = input('URL: ')\ntry:\n    with urlopen(url, timeout=2) as response:\n        record = json.load(response)\nexcept HTTPError as error:\n    print(f'Request failed: HTTP {error.code}')\nexcept URLError:\n    print('Request failed')\nexcept json.JSONDecodeError:\n    print('Invalid JSON response')\nelse:\n    print(record.get('name', 'Unknown'))\n",
        difficulty="intermediate", mode="http",
    ),
    "unique_values": Exercise(
        "unique_values", "Keep the first occurrence of each value",
        "Implement unique_values(values) returning unique values in their original order.",
        "def unique_values(values):\n    pass\n",
        ((([2, 1, 2, 3, 1],), [2, 1, 3]), (([],), [])),
        ("Track values you have seen.", "Append unseen values to a new list as you walk the input."),
        "def unique_values(values):\n    seen = set()\n    result = []\n    for value in values:\n        if value not in seen:\n            seen.add(value)\n            result.append(value)\n    return result\n", function="unique_values",
    ),
    "group_transactions": Exercise(
        "group_transactions", "Group transaction totals",
        "Implement group_transactions(rows) where rows contain (category, amount), returning totals by category.",
        "def group_transactions(rows):\n    pass\n",
        ((([("food", 4), ("travel", 3), ("food", 2)],), {"food": 6, "travel": 3}), (([],), {})),
        ("Start with an empty dictionary.", "Add each amount to the current total for its category."),
        "def group_transactions(rows):\n    totals = {}\n    for category, amount in rows:\n        totals[category] = totals.get(category, 0) + amount\n    return totals\n", function="group_transactions",
    ),
    "top_words": Exercise(
        "top_words", "Count words ignoring case",
        "Implement top_words(text) returning a dictionary of lowercase word counts split on whitespace.",
        "def top_words(text):\n    pass\n",
        ((("Red blue red",), {"red": 2, "blue": 1}), (("",), {})),
        ("Split the text into words and lowercase each one.", "Increment a dictionary count for each word."),
        "def top_words(text):\n    counts = {}\n    for word in text.lower().split():\n        counts[word] = counts.get(word, 0) + 1\n    return counts\n", function="top_words",
    ),
    "project_plan": Exercise(
        "project_plan", "Build a project checklist",
        "Implement project_plan(features) returning a list with setup first, each feature in order, and tests last.",
        "def project_plan(features):\n    pass\n",
        (((["add task", "list tasks"],), ["setup", "add task", "list tasks", "tests"]), (([],), ["setup", "tests"])),
        ("Create a list containing setup.", "Extend it with features, then append tests."),
        "def project_plan(features):\n    return ['setup', *features, 'tests']\n", function="project_plan",
    ),
    "repeat_message": Exercise(
        "repeat_message", "Repeat a message",
        "Implement repeat_message(message, count) returning the message repeated count times, separated by spaces. Return an empty string when count is zero.",
        "def repeat_message(message, count):\n    # Return the repeated message.\n    pass\n",
        ((("Hi", 3), "Hi Hi Hi"), (("Go", 1), "Go"), (("Stop", 0), "")),
        ("Build a sequence containing count copies of message.", "Use ' '.join(...) to place one space between the copies."),
        "def repeat_message(message, count):\n    return ' '.join([message] * count)\n", function="repeat_message",
    ),
    "profile_label": Exercise(
        "profile_label", "Label a profile value",
        "Implement profile_label(name, age) returning a dictionary with the supplied name and age under those keys.",
        "def profile_label(name, age):\n    pass\n",
        ((("Ada", 36), {"name": "Ada", "age": 36}), (("Grace", 85), {"name": "Grace", "age": 85})),
        ("Return a dictionary literal.", "Use the keys 'name' and 'age' and map each to its matching parameter."),
        "def profile_label(name, age):\n    return {'name': name, 'age': age}\n", function="profile_label",
    ),
    "calculate_total": Exercise(
        "calculate_total", "Calculate a purchase total",
        "Implement calculate_total(price, quantity, tax_rate) returning price times quantity plus tax. tax_rate is a decimal fraction, such as 0.2 for 20 percent.",
        "def calculate_total(price, quantity, tax_rate):\n    pass\n",
        (((10, 2, 0.2), 24), ((5, 1, 0), 5), ((2.5, 4, 0.1), 11)),
        ("Calculate the subtotal before tax.", "Multiply the subtotal by 1 + tax_rate to include tax."),
        "def calculate_total(price, quantity, tax_rate):\n    subtotal = price * quantity\n    return subtotal * (1 + tax_rate)\n", function="calculate_total",
    ),
    "shipping_cost": Exercise(
        "shipping_cost", "Choose a shipping cost",
        "Implement shipping_cost(order_total): return 0 for totals of at least 50, 5 for totals of at least 25, and 10 otherwise.",
        "def shipping_cost(order_total):\n    pass\n",
        (((75,), 0), ((50,), 0), ((25,), 5), ((10,), 10)),
        ("There are three possible ranges.", "Check the largest threshold first with if / elif / else."),
        "def shipping_cost(order_total):\n    if order_total >= 50:\n        return 0\n    if order_total >= 25:\n        return 5\n    return 10\n", function="shipping_cost", difficulty="intermediate",
    ),
    "count_matches": Exercise(
        "count_matches", "Count matching values",
        "Implement count_matches(values, target) returning how many items equal target.",
        "def count_matches(values, target):\n    pass\n",
        ((([1, 2, 1, 3, 1], 1), 3), (([], 0), 0), ((("a", "b", "a"), "a"), 2)),
        ("Start a counter at zero.", "Visit each value and increase the counter when it equals target."),
        "def count_matches(values, target):\n    count = 0\n    for value in values:\n        if value == target:\n            count += 1\n    return count\n", function="count_matches",
    ),
    "make_counter": Exercise(
        "make_counter", "Build values with a closure",
        "Implement make_counter(start, step, calls) using an inner function that remembers the current value. Return a list of the next calls values, each increased by step.",
        "def make_counter(start, step, calls):\n    # Define an inner function and collect its returned values.\n    pass\n",
        (((3, 2, 3), [5, 7, 9]), ((0, 1, 3), [1, 2, 3]), ((5, 4, 0), [])),
        ("Define an inner function that can access a value from make_counter.", "Update that remembered value with nonlocal, then call the inner function once per requested result."),
        "def make_counter(start, step, calls):\n    current = start\n    def increment():\n        nonlocal current\n        current += step\n        return current\n    return [increment() for _ in range(calls)]\n", function="make_counter", difficulty="intermediate",
    ),
    "invert_lookup": Exercise(
        "invert_lookup", "Invert a lookup dictionary",
        "Implement invert_lookup(mapping) returning a new dictionary whose keys are the original values and whose values are the original keys. Assume values are unique and hashable.",
        "def invert_lookup(mapping):\n    pass\n",
        ((({"ada": "1", "grace": "2"},), {"1": "ada", "2": "grace"}), (({},), {})),
        ("Create a new empty dictionary.", "Loop over key-value pairs and assign result[value] = key."),
        "def invert_lookup(mapping):\n    return {value: key for key, value in mapping.items()}\n", function="invert_lookup", difficulty="intermediate",
    ),
}


def run_exercise(exercise: Exercise, source: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Run submitted source and table-driven cases in an isolated child process."""
    if exercise.mode == "http":
        harness = '''import contextlib, io, json, sys, traceback
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

CASES = json.loads(%r)
current_case = 0
try:
    with open("submission.py", encoding="utf-8") as source_file:
        source = source_file.read()
    for index, case in enumerate(CASES, 1):
        current_case = index
        body, status, expected = case
        url = "https://fixture.invalid/record/%%d" %% index
        if status == 0:
            mocked_request = patch("urllib.request.urlopen", side_effect=URLError("fixture connection error"))
        elif status >= 400:
            error = HTTPError(url, status, "fixture HTTP error", {}, BytesIO(body.encode("utf-8")))
            mocked_request = patch("urllib.request.urlopen", side_effect=error)
        else:
            mocked_request = patch("urllib.request.urlopen", return_value=BytesIO(body.encode("utf-8")))
        output = io.StringIO()
        previous_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(url + "\\n")
            with mocked_request as request, contextlib.redirect_stdout(output):
                exec(compile(source, "submission.py", "exec"), {})
            request_timeout = None if request.call_args is None else request.call_args.kwargs.get("timeout")
            if not isinstance(request_timeout, (int, float)) or request_timeout <= 0:
                raise AssertionError("Case %%d: HTTP requests must set a finite timeout" %% index)
        finally:
            sys.stdin = previous_stdin
        actual = output.getvalue()
        if actual != expected:
            raise AssertionError("Case %%d with fixture HTTP %%d: expected output %%r, got %%r" %% (index, status, expected, actual))
    print("PASS:%d")
except BaseException as error:
    print("FAIL:" + ("Case %%d: " %% current_case if current_case else "") + type(error).__name__ + ": " + str(error))
    traceback.print_exc()
    raise SystemExit(1)
''' % (json.dumps(exercise.tests), len(exercise.tests))
    elif exercise.mode == "script":
        harness = '''import contextlib, io, json, os, sys, traceback

CASES = json.loads(%r)
try:
    with open("submission.py", encoding="utf-8") as source_file:
        source = source_file.read()
    for index, case in enumerate(CASES, 1):
        if len(case) == 2:
            provided, expected = case
            files = {}
        else:
            provided, expected, files = case
        case_dir = os.path.abspath(os.path.join("cases", str(index)))
        os.makedirs(case_dir, exist_ok=True)
        for relative, contents in files.items():
            target = os.path.abspath(os.path.join(case_dir, relative))
            if os.path.commonpath((case_dir, target)) != case_dir:
                raise AssertionError("Unsafe test fixture path: " + relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fixture:
                fixture.write(contents)
        output = io.StringIO()
        previous_stdin = sys.stdin
        previous_directory = os.getcwd()
        try:
            os.chdir(case_dir)
            sys.stdin = io.StringIO(provided)
            with contextlib.redirect_stdout(output):
                exec(compile(source, "submission.py", "exec"), {})
        finally:
            sys.stdin = previous_stdin
            os.chdir(previous_directory)
        actual = output.getvalue()
        if actual != expected:
            raise AssertionError("Case %%d with input %%r: expected output %%r, got %%r" %% (index, provided, expected, actual))
    print("PASS:%d")
except BaseException as error:
    print("FAIL:" + type(error).__name__ + ": " + str(error))
    traceback.print_exc()
    raise SystemExit(1)
''' % (json.dumps(exercise.tests), len(exercise.tests))
    else:
        harness = '''import json, traceback

CASES = json.loads(%r)
FUNCTION_NAME = %r
try:
    namespace = {}
    with open("submission.py", encoding="utf-8") as source_file:
        source = source_file.read()
    exec(compile(source, "submission.py", "exec"), namespace)
    function = namespace.get(FUNCTION_NAME)
    if not callable(function):
        raise AssertionError("Define the required " + FUNCTION_NAME + " function.")
    for index, case in enumerate(CASES, 1):
        args, expected = case
        actual = function(*args)
        if actual != expected:
            raise AssertionError("Case %%d with inputs %%r: expected %%r, got %%r" %% (index, args, expected, actual))
    print("PASS:%d")
except BaseException as error:
    print("FAIL:" + type(error).__name__ + ": " + str(error))
    traceback.print_exc()
    raise SystemExit(1)
''' % (json.dumps(exercise.tests), exercise.function, len(exercise.tests))
    try:
        with tempfile.TemporaryDirectory(prefix="ghost-exercise-") as directory:
            workdir = Path(directory)
            (workdir / "submission.py").write_text(source, encoding="utf-8")
            (workdir / "runner.py").write_text(harness, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-I", "runner.py"], cwd=workdir,
                capture_output=True, text=True, timeout=timeout, check=False,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
            )
        output = (result.stdout + result.stderr).strip()
        success_marker = f"PASS:{len(exercise.tests)}"
        if result.returncode == 0 and success_marker in result.stdout.splitlines():
            return True, f"All {len(exercise.tests)} test cases passed."
        if result.returncode != 0 and "FAIL:" in result.stdout:
            message = result.stdout.split("FAIL:", 1)[1].splitlines()[0]
            return False, message
        return False, output or "The exercise process exited without a result."
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {timeout:g} seconds. Check for an infinite loop."
    except OSError as error:
        return False, f"Could not run Python: {error}"


def edit_submission(exercise: Exercise) -> str | None:
    """Open the learner's configured editor and return the resulting source."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="ghost-edit-") as directory:
            path = Path(directory) / f"{exercise.id}.py"
            path.write_text(exercise.starter, encoding="utf-8")
            result = subprocess.run([*shlex.split(editor), str(path)], check=False)
            if result.returncode != 0:
                return None
            return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

