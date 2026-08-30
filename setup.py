from setuptools import find_packages, setup

setup(
    name="adblock-rule-collection",
    version="1.1.0",
    description="合并、去重、生成广告拦截与 DNS 过滤规则",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=["requests>=2.31.0", "PyYAML>=6.0"],
    entry_points={
        "console_scripts": [
            "adblock-collection=adblock_collection.cli:main",
        ],
    },
)
