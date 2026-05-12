from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("koda.llm", includes=["models.json"])
