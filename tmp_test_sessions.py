from services.payments import PaymentService

errors=0
for i in range(50):
    try:
        svc=PaymentService()
        svc.get_history(1)
    except Exception as e:
        errors+=1
print('done', 'errors=', errors)
