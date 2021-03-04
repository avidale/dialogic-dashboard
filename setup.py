import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dialogic_dashboard",
    version="0.0.1",
    author="David Dale",
    author_email="dale.david@mail.ru",
    description="A dashboard for viewing logs of chat bots",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/avidale/dialogic-dashboard",
    packages=setuptools.find_packages(),
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'dnspython',
        'flask',
        'flask-login',
        'flask-bootstrap',
        'pymongo',
        'attrs',
    ],
)
