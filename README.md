# Crawldata

Thu muc nay dung de cao, loc va tao dataset gia dat Da Nang cho ung dung du doan.

## Cau truc file

```text
crawldata/
├── scrape_alonhadat_land_list.py   # Cao du lieu dat tu Alonhadat
├── scrape_homedy_land_list.py      # Cao du lieu dat tu Homedy
├── build_danang_ml_dataset.py      # Loc raw data va tao dataset sach
└── data/
    ├── danang_land_raw.csv         # Du lieu tho sau khi cao
    └── danang_land_dataset.csv     # Dataset sach dung cho model
```

## Thu tu chay

### 1. Cao du lieu tu Alonhadat

```powershell
cd D:\Python\crawldata
python scrape_alonhadat_land_list.py --pages 30 --output data\danang_land_raw.csv
```

### 2. Cao du lieu tu Homedy

```powershell
cd D:\Python\crawldata
python scrape_homedy_land_list.py --pages 25 --output data\danang_land_raw.csv
```

Hai script scraper se append du lieu moi vao:

```text
data/danang_land_raw.csv
```

Script tu bo qua URL da ton tai, nen co the chay lai de cap nhat them du lieu moi.

### 3. Loc va tao dataset sach

```powershell
cd D:\Python\crawldata
python build_danang_ml_dataset.py --input data\danang_land_raw.csv --output data\danang_land_dataset.csv
```

Script nay se:

- chi lay tin dat
- bo dong thieu dien tich, gia, quan/huyen
- sua loi gia dang `trieu/m2`
- dien gia tri thieu cho `frontage_m`, `road_width_m`
- loc gia tri bat thuong
- loc trung URL
- loc trung theo thong so chinh
- loc trung gan giong theo title, dien tich va gia
- loc outlier theo don gia tung quan/huyen

Output:

```text
data/danang_land_dataset.csv
```

### 4. Copy dataset sang ung dung Django

```powershell
Copy-Item D:\Python\crawldata\data\danang_land_dataset.csv D:\Python\HousePrice\data\danang_land_dataset.csv -Force
```

### 5. Chay web

```powershell
cd D:\Python\HousePrice
python manage.py runserver
```

Mo trinh duyet:

```text
http://127.0.0.1:8000/
```

## Kiem tra nhanh

### Kiem tra script co loi cu phap khong

```powershell
cd D:\Python
python -m py_compile crawldata\scrape_alonhadat_land_list.py crawldata\scrape_homedy_land_list.py crawldata\build_danang_ml_dataset.py
```

### Kiem tra dataset sach

```powershell
cd D:\Python
python -c "import pandas as pd; df=pd.read_csv('crawldata/data/danang_land_dataset.csv'); print(df.shape); print(df['property_type'].value_counts()); print(df['price_per_m2_million'].describe())"
```

### Kiem tra model Django

```powershell
cd D:\Python
python -c "from pathlib import Path; from HousePrice.predictor.ml import get_model; m=get_model(Path('HousePrice/data/danang_land_dataset.csv')); print(m.row_count, m.rmse, m.mae, m.r2)"
```

## Chay mot luot day du

```powershell
cd D:\Python\crawldata
python scrape_alonhadat_land_list.py --pages 30 --output data\danang_land_raw.csv
python scrape_homedy_land_list.py --pages 25 --output data\danang_land_raw.csv
python build_danang_ml_dataset.py --input data\danang_land_raw.csv --output data\danang_land_dataset.csv
Copy-Item D:\Python\crawldata\data\danang_land_dataset.csv D:\Python\HousePrice\data\danang_land_dataset.csv -Force
cd D:\Python\HousePrice
python manage.py runserver
```

