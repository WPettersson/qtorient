from setuptools import setup, find_packages
setup(
    name="QtOrient",
    version="0.1",
    packages=find_packages(),
    entry_points={'console_scripts':
                  [ 'qtorient = qtorient.__main__:main',
                   ]
                  },
    author="William Pettersson",
    author_email="opensource@ewpettersson.se",
    keywords="sensor orientation tablet",
    url="https://github.com/WPettersson/qtorient",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
    ]
)
