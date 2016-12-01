import requests, json, urllib.parse, time, random, datetime, threading

# Constant
base_url = 'http://www.supremenewyork.com'
headers = {'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 6_1_4 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10B350 Safari/8536.25'}

class Product(object):
    def __init__(self, category, keywords, colors, sizes, quantity):
        self.category = category
        self.keywords = keywords
        self.colors = colors
        self.sizes = sizes
        self.quantity = quantity
        self.carted = False
        self.variants = []
        self.id = None

class Task(object): 
    def __init__(self, products, interval=1, ghost=1, proxies={}):
        self.id = random.getrandbits(128)
        self.active = False
        self.parent = None
        self.products = products
        self.interval = interval
        self.ghost = ghost
        self.session = requests.session()
        self.session.proxies.update(proxies)
        
    def toggle(self):
        self.active = not self.active

class Card(object):
    def __init__(self, cardtype, number, month, year, cvv):
        self.cardtype = cardtype
        self.number = number
        self.month = month
        self.year = year
        self.cvv = cvv
        
class Address(object):
    def __init__(self, address_1, address_2, zipcode, city, state, country='USA'):
        self.address_1 = address_1
        self.address_2 = address_2
        self.zipcode = zipcode
        self.city = city
        self.state = state
        self.country = country

class Account(object):
    def __init__(self, first_name, last_name, email, tel, address, card, tasks=[]):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.tel = tel
        self.address = address
        self.card = card
        self.tasks = tasks
        
    def register_task(self, task):
        if task.parent is not None:
            task.parent.remove_task(task)
        task.parent = self
        self.tasks.append(task)
        
    def remove_task(self, task):
        task.parent = None
        self.tasks.remove(task)
        
    def stop_all_tasks(self):
        for task in (tasks for tasks in self.tasks if tasks.active):
            task.toggle()
            
    def start_all_tasks(self):
        for task in (tasks for tasks in self.tasks if not tasks.active):
            task.toggle()

def log(event):
    print(str(datetime.datetime.now().strftime('%H:%M:%S')) + ' ::: ' + str(event))

# Returns the ID for first product that matches the keywords
def get_product_id(task, product):
    log('Getting product ID for keywords ' + str(product.keywords))
    response = task.session.get(base_url + '/mobile_stock.json', headers=headers)
    response_json = json.loads(response.text)
    product_ids = [temp_product['id'] for temp_product in response_json['products_and_categories'][product.category.title()] if all(keyword.lower() in temp_product['name'].lower() for keyword in product.keywords)]
    product_id = None
    if product_ids:
        product_id = product_ids[0]
        log('Got product ID for keywords ' + str(product.keywords) + ': ' + str(product_id))
    else:
        log('Count not get product ID for keywords ' + str(product.keywords))
    return product_id   

# Returns the matching variant IDs for a product
def get_variant_ids(task, product):
    log('Getting variant IDs for product ' + str(product.id))
    response = task.session.get(base_url + '/shop/' + str(product.id) + '.json', headers=headers)
    response_json = json.loads(response.text)
    color_matches = [variant for variant in response_json['styles'] if (product.colors[0].lower() == 'any' or any(variant['name'].lower() == color.lower() for color in product.colors))]
    variant_ids = []
    for variant in color_matches:
        for size in variant['sizes']:
            if ((product.sizes[0].lower() == 'any' or any(size['name'].lower() == task_size.lower() for task_size in product.sizes)) and size['stock_level'] > 0):
                variant_ids.append(size['id'])
    if variant_ids:
        log('Got variant IDs for product ' + str(product.id) + ': ' + str(variant_ids))
    return variant_ids

# Adds a product to cart given the product ID
def add_to_cart(task, product, variant):
    log('Adding ' + str(product.quantity) + 'x product ' + str(product.id) + ' in variant ' + str(variant) + ' to cart')
    payload = {
        'size': variant,
        'qty': product.quantity
    }
    response = task.session.post(base_url + '/shop/' + str(product.id) + '/add.json', data=payload, headers=headers)
    response_json = json.loads(response.text)
    if response_json and not product.carted:
        product.carted = True
        log('Added ' + str(product.quantity) + 'x product ' + str(product.id) + ' in variant ' + str(variant) + ' to cart')

    
# Checks out on all items in a task's cart
def checkout(account, task):
    cookie_sub_dict = {}
    for product in task.products:
        cookie_sub_dict[product.id] = product.quantity
    cookie_sub_string = urllib.parse.quote(str(cookie_sub_dict))
    log('Checking out cart for task ' + str(task.id))

    payload = {
        'store_credit_id': '',
        'from_mobile': '1',
        'cookie-sub': cookie_sub_string,
        'same_as_billing_address': '1',
        'order[billing_name]': account.first_name + ' ' + account.last_name,
        'order[email]': account.email,
        'order[tel]': account.tel,
        'order[billing_address]': account.address.address_1,
        'order[billing_address_2]': account.address.address_2,
        'order[billing_zip]': account.address.zipcode,
        'order[billing_city]': account.address.city,
        'order[billing_state]': account.address.state,
        'order[billing_country]': account.address.country,
        'store_address': '1',
        'credit_card[type]': account.card.cardtype,
        'credit_card[cnb]': account.card.number,
        'credit_card[month]': account.card.month,
        'credit_card[year]': account.card.year,
        'credit_card[vval]': account.card.cvv,
        'order[terms]': '0',
        'order[terms]': '1'
    }

    time.sleep(task.ghost)
    response = task.session.post('https://www.supremenewyork.com/checkout.json', data=payload, headers=headers)
    res_json = json.loads(response.text)
    if res_json['status'] != 'failed':
        log('Checked out cart for task ' + str(task.id))
    else:
        log('Error while checking out cart for task ' + str(task.id))
        print(res_json)

def add_product(task, product):
    product.id = None
    while product.id is None:
        product.id = get_product_id(task, product)
        time.sleep(1)
    while not product.variants:
        product.variants = get_variant_ids(task, product)
        time.sleep(1)

    threads = []
    for variant in product.variants:
        thread = threading.Thread(target=add_to_cart, args=(task, product, variant))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

def run_task(account, task):
    threads = []
    for product in task.products:
        thread = threading.Thread(target=add_product(task, product))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    checkout(account, task)

def main():
    accounts = [
        Account('FirstName', 'LastName', 'email@domain.com', 'XXX-XXX-XXXX', Address('123 Main Street', 'APT 1A', '12345', 'Brooklyn', 'NY'), Card('visa', 'XXXX XXXX XXXX XXXX', 'XX', 'XXXX', 'XXX')),
    ]

    tasks = [
        Task(products=[
                Product(category='accessories', keywords=['hanes', 'tagless'], colors=['white'], sizes=['any'], quantity=1),
                Product(category='accessories', keywords=['hanes', 'tagless'], colors=['black'], sizes=['any'], quantity=1)
            ],
            interval=1, 
            ghost=1, 
            proxies={}
        ),
        Task(products=[
                Product(category='accessories', keywords=['hanes', 'socks'], colors=['any'], sizes=['any'], quantity=1)
            ],
            interval=1, 
            ghost=1, 
            proxies={}
        )
    ]

    accounts[0].register_task(tasks[0])
    accounts[0].register_task(tasks[1])
    for task in accounts[0].tasks:
        thread = threading.Thread(target=run_task, args=(accounts[0], task))
        thread.start()
        
if __name__ == '__main__':
    main()