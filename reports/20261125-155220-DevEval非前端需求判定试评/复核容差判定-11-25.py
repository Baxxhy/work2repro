from decimal import Decimal as D
expected = D('1.0')
for candidate in ['1.0', '1.0000000000005', '1.000000000002']:
    diff = abs(D(candidate) - expected)
    print(candidate, '允许' if diff <= D('1e-12') else '违规', '精确相等断言', D(candidate) == expected)
