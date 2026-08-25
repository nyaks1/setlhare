prices = {"apple": 12, "pear": 8}

def checkout(cart):
    total = 0
    for item in cart:
        total += prices[item]
    return total


print(checkout(["apple", "mango", "pear"]))
