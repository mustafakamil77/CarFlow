# CarFlow — نظام إدارة أسطول المركبات

## نظرة عامة
- CarFlow نظام مبني على Django لإدارة الأسطول: المركبات، الوقود، الصيانة، السائقين، والتقارير.
- يوفر CRUD كامل للمركبات، استيراد سجلات الوقود من Excel، طلبات الصيانة مع تنبيهات بريدية، تقارير ولوحة معلومات بواجهات حديثة.
- يعتمد على Tailwind عبر CDN، Leaflet للخرائط، Chart.js للرسوم البيانية، وReportLab لتوليد PDF.

## المزايا الأساسية
- إدارة مركبات كاملة (CRUD) مع صلاحيات مبنية على الأدوار.
- خرائط Leaflet لعرض مواقع المركبات.
- استيراد Excel لسجلات الوقود مع تحقق ودمج آمن.
- طلبات صيانة مع رفع صور وتنبيهات بريدية عبر Django Q.
- لوحة تقارير بالرسوم البيانية + تصدير PDF.

## التقنيات
- Django 5، SQLite (افتراضيًا)، Django Q للمهام غير المتزامنة.
- مكتبات: Pillow (صور)، pandas + openpyxl (Excel)، Chart.js (CDN)، Leaflet (CDN)، ReportLab (PDF).
- الواجهات: Tailwind عبر CDN وقالب أساسي موحد.

## المتطلبات
- Python 3.10+
- بيئة افتراضية مفعلة
- حزم المشروع:

```bash
pip install -r requirements.txt
```

## الإعداد السريع
1) إنشاء قاعدة البيانات وتشغيل المهاجرات:
- Linux/macOS:

```bash
python src/manage.py makemigrations
python src/manage.py migrate
```

- Windows:

```bash
python src\manage.py makemigrations
python src\manage.py migrate
```

2) إنشاء مستخدم مسؤول:

```bash
python src/manage.py createsuperuser
```

3) تشغيل عُقد المهام غير المتزامنة (Django Q) في نافذة مستقلة:

```bash
python src/manage.py qcluster
```

4) تشغيل الخادم:

```bash
python src/manage.py runserver
```

5) تسجيل الدخول:
- صفحة الدخول القياسية: `/accounts/login/`

## البنية العامة للتطبيقات
- accounts: الأدوار والتعيينات DriverAssignment + قوالب الدخول.
- fleet: المركبات، الحالات، الصور، واجهات CRUD + خرائط.
- fuel: نموذج سجلات الوقود واستيراد Excel.
- maintenance: طلبات الصيانة والصور + إشعارات بريدية.
- reports: لوحة معلومات ورسوم بيانية + PDF.
- project: الإعدادات العامة وروابط المشروع.

## الأدوار والصلاحيات
- Fleet Manager: صلاحيات CRUD كاملة على المركبات.
- Maintenance Technician: عرض فقط في الأسطول؛ إدارة الصيانة.
- Driver: عرض المركبات المخصصة له فقط.
- المشرف (superuser): يتجاوز جميع القيود الإدارية.
- يتم إنشاء المجموعات تلقائيًا عند تشغيل التطبيق لأول مرة.

## نقاط الدخول وروابط مهمة
- الصفحة الرئيسية: `/`
- لوحة الإدارة: `/admin/`
- الدخول/الخروج: `/accounts/login/`, `/accounts/logout/`
- الأسطول:
  - قائمة المركبات: `/fleet/cars/`
  - إنشاء: `/fleet/cars/create/`
  - تفاصيل: `/fleet/cars/<id>/`
  - تعديل: `/fleet/cars/<id>/edit/`
  - حذف (ناعم): `/fleet/cars/<id>/delete/`
  - خريطة الأسطول: `/fleet/cars/map/`
- الصيانة:
  - قائمة الطلبات: `/maintenance/requests/`
  - إنشاء: `/maintenance/requests/new/`
  - تفاصيل: `/maintenance/requests/<id>/`
  - رفع صورة: `/maintenance/requests/<id>/images/upload/`
- الوقود:
  - استيراد Excel: `/fuel/upload/`
- التقارير:
  - لوحة معلومات: `/reports/dashboard/`
  - PDF: `/reports/pdf/kpis/`

## نموذج المركبة (Car)
- الحقول الأساسية:
  - plate_number (فريد ومفهرس)، brand، model، year
  - current_latitude، current_longitude
  - status (active/inactive/maintenance)
  - notes (اختياري)، is_active (حذف ناعم)
  - created_at، updated_at
- الفهارس: plate_number, status, is_active
- الترتيب: أحدث أولًا

## واجهات CRUD للمركبات
- قائمة: بحث سريع (plate/brand/model) + فلترة الحالة + فرز أعمدة + ترقيم.
- تفاصيل: معلومات كاملة + إحصائيات سريعة (conditions, maintenance) + خريطة Leaflet.
- إنشاء/تعديل: نموذج موحد مع تحقق (السنة، خط العرض/الطول) ورسالة نجاح.
- حذف: تأكيد عبر نافذة/نموذج؛ حذف ناعم عبر is_active.

## الخرائط (Leaflet)
- في التفاصيل: خريطة بمؤشر للمركبة (lat/lon) مع نافذة منبثقة plate/model.
- خريطة الأسطول: جميع المركبات ذات إحداثيات محددة.

## استيراد الوقود من Excel
- الصفحة: `/fuel/upload/`
- الأعمدة المطلوبة:

```csv
plate_number,date,liters,cost,odometer
```

- التحقق:
  - مطابقة plate_number إلى Car
  - تاريخ صالح، أرقام صحيحة للـ liters/cost/odometer
  - قيد فريد: (car, date, odometer) لمنع التكرار
- الإدراج:
  - bulk_create مع ignore_conflicts
  - ملخص يوضح عدد السجلات التي تمت إضافتها والأخطاء.

## الصيانة والتنبيهات
- إنشاء MaintenanceRequest يرسل مهمة بريدية عبر Django Q إلى مجموعة "Maintenance Technician".
- رفع صور لكل طلب صيانة، عرضها داخل التفاصيل.

## التقارير
- لوحة معلومات تجمع إجمالي الوقود والتكلفة لكل مركبة مع Chart.js.
- تصدير PDF بسيط لملخصات الوقود عبر ReportLab.

## الواجهات (Tailwind)
- قالب أساسي `src/templates/base.html` مع شريط تنقل ورسائل Toast.
- جميع الصفحات الأساسية تمتد من القالب وتستخدم عناصر Tailwind.

## إدارة الوسائط
- رفع صور المركبات والصيانة يعمل مع Pillow.
- تأكد من ضبط MEDIA_ROOT وMEDIA_URL في الإعدادات، وخدمة الوسائط في وضع DEBUG.

## الأداء
- فهارس على الحقول المستخدمة في الفرز/الفلترة.
- ترقيم الصفحات (10 في قائمة المركبات).
- استخدام الاستعلامات المفلترة حسب الدور لتقليل البيانات.

## التطوير
- تشغيل الخادم والتطوير عبر `runserver`، وتشغيل Q عبر `qcluster` لمعالجة المهام.
- إضافة الوظائف أو التعديلات ضمن التطبيقات المعنية مع الالتزام بالأنماط الحالية.

## استكشاف الأخطاء
- خطأ "no such column": شغّل المهاجرات بعد تعديل النماذج.
- 403 عند الإنشاء/التعديل: تأكد من أن المستخدم في مجموعة "Fleet Manager" أو مشرف.
- البريد لا يصل: استخدم EMAIL_BACKEND مناسب (مثل console) أثناء التطوير وشغّل qcluster.

## الترخيص
- داخلي/تعليمي. يمكن تعديل الترخيص حسب الحاجة.
