# ZAP Scanning Report

ZAP by [Checkmarx](https://checkmarx.com/).


## Summary of Alerts

| Risk Level | Number of Alerts |
| --- | --- |
| High | 0 |
| Medium | 0 |
| Low | 2 |
| Informational | 4 |




## Insights

| Level | Reason | Site | Description | Statistic |
| --- | --- | --- | --- | --- |
| Medium | Exceeded High | http://frontend:8080 | Percentage of responses with status code 4xx | 99 % |
| Low | Warning |  | ZAP warnings logged - see the zap.log file for details | 75    |
| Info | Informational | http://frontend:8080 | Percentage of endpoints with content type application/json | 88 % |
| Info | Informational | http://frontend:8080 | Percentage of endpoints with content type text/html | 11 % |
| Info | Informational | http://frontend:8080 | Percentage of endpoints with method DELETE | 5 % |
| Info | Informational | http://frontend:8080 | Percentage of endpoints with method GET | 62 % |
| Info | Informational | http://frontend:8080 | Percentage of endpoints with method PATCH | 2 % |
| Info | Informational | http://frontend:8080 | Percentage of endpoints with method POST | 26 % |
| Info | Informational | http://frontend:8080 | Percentage of endpoints with method PUT | 3 % |
| Info | Informational | http://frontend:8080 | Count of total endpoints | 93    |







## Alerts

| Name | Risk Level | Number of Instances |
| --- | --- | --- |
| A Server Error response code was returned by the server | Low | 1 |
| Unexpected Content-Type was returned | Low | 12 |
| A Client Error response code was returned by the server | Informational | 89 |
| Authentication Request Identified | Informational | 2 |
| Information Disclosure - Sensitive Information in URL | Informational | 4 |
| Non-Storable Content | Informational | Systemic |




## Alert Detail



### [ A Server Error response code was returned by the server ](https://www.zaproxy.org/docs/alerts/100000/)



##### Low (High)

### Description

A response code of 500 was returned by the server.
This may indicate that the application is failing to handle unexpected input correctly.
Raised by the 'Alert on HTTP Response Code Error' script

* URL: http://frontend:8080/api/auth/register
  * Node Name: `http://frontend:8080/api/auth/register ()({email,full_name,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `500`
  * Other Info: ``


Instances: 1

### Solution



### Reference



#### CWE Id: [ 388 ](https://cwe.mitre.org/data/definitions/388.html)


#### WASC Id: 20

#### Source ID: 4

### [ Unexpected Content-Type was returned ](https://www.zaproxy.org/docs/alerts/100001/)



##### Low (High)

### Description

A Content-Type of text/html was returned by the server.
This is not one of the types expected to be returned by an API.
Raised by the 'Alert on Unexpected Content Types' script

* URL: http://frontend:8080
  * Node Name: `http://frontend:8080`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/
  * Node Name: `http://frontend:8080/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/5368144093155689472
  * Node Name: `http://frontend:8080/5368144093155689472`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/6075324395015032302
  * Node Name: `http://frontend:8080/6075324395015032302`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/api
  * Node Name: `http://frontend:8080/api`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/computeMetadata/v1/
  * Node Name: `http://frontend:8080/computeMetadata/v1/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/latest/meta-data/
  * Node Name: `http://frontend:8080/latest/meta-data/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/metadata/instance
  * Node Name: `http://frontend:8080/metadata/instance ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/metadata/v1
  * Node Name: `http://frontend:8080/metadata/v1 ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/opc/v1/instance/
  * Node Name: `http://frontend:8080/opc/v1/instance/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/opc/v2/instance/
  * Node Name: `http://frontend:8080/opc/v2/instance/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``
* URL: http://frontend:8080/openstack/latest/meta_data.json
  * Node Name: `http://frontend:8080/openstack/latest/meta_data.json ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `text/html`
  * Other Info: ``


Instances: 12

### Solution



### Reference




#### Source ID: 4

### [ A Client Error response code was returned by the server ](https://www.zaproxy.org/docs/alerts/100000/)



##### Informational (High)

### Description

A response code of 401 was returned by the server.
This may indicate that the application is failing to handle unexpected input correctly.
Raised by the 'Alert on HTTP Response Code Error' script

* URL: http://frontend:8080/api/authors/10
  * Node Name: `http://frontend:8080/api/authors/10`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/10
  * Node Name: `http://frontend:8080/api/books/10`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/categories/10
  * Node Name: `http://frontend:8080/api/categories/10`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/copies/10
  * Node Name: `http://frontend:8080/api/copies/10`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/users/10
  * Node Name: `http://frontend:8080/api/users/10`
  * Method: `DELETE`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/
  * Node Name: `http://frontend:8080/api/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/1850581243179561585
  * Node Name: `http://frontend:8080/api/1850581243179561585`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/audit%3Faction=&entity_type=&user_email=&date_from=&date_to=&page=1&size=50
  * Node Name: `http://frontend:8080/api/audit (action,date_from,date_to,entity_type,page,size,user_email)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/auth
  * Node Name: `http://frontend:8080/api/auth`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/
  * Node Name: `http://frontend:8080/api/auth/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/4870914058993572475
  * Node Name: `http://frontend:8080/api/auth/4870914058993572475`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/actuator/health
  * Node Name: `http://frontend:8080/api/auth/actuator/health`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/me
  * Node Name: `http://frontend:8080/api/auth/me`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/authors
  * Node Name: `http://frontend:8080/api/authors`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/authors%3Fq=
  * Node Name: `http://frontend:8080/api/authors (q)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/authors/5508103647953283145
  * Node Name: `http://frontend:8080/api/authors/5508103647953283145`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/api/books
  * Node Name: `http://frontend:8080/api/books`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books%3Fq=&category_id=&author_id=&year_from=&year_to=&available_only=false&sort=title&page=1&size=20
  * Node Name: `http://frontend:8080/api/books (author_id,available_only,category_id,page,q,size,sort,year_from,year_to)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/10
  * Node Name: `http://frontend:8080/api/books/10`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/10/8137727295348951629
  * Node Name: `http://frontend:8080/api/books/10/8137727295348951629`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/books/10/copies
  * Node Name: `http://frontend:8080/api/books/10/copies`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/2628958061639168294
  * Node Name: `http://frontend:8080/api/books/2628958061639168294`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/lookup
  * Node Name: `http://frontend:8080/api/books/lookup`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/lookup/3273324058927875592
  * Node Name: `http://frontend:8080/api/books/lookup/3273324058927875592`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/lookup/isbn
  * Node Name: `http://frontend:8080/api/books/lookup/isbn`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/categories
  * Node Name: `http://frontend:8080/api/categories`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/categories/3505157466451937707
  * Node Name: `http://frontend:8080/api/categories/3505157466451937707`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/api/copies
  * Node Name: `http://frontend:8080/api/copies`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/copies/
  * Node Name: `http://frontend:8080/api/copies/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/copies/5243915559617700152
  * Node Name: `http://frontend:8080/api/copies/5243915559617700152`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/api/dashboard%3Fdate_from=&date_to=&category_id=
  * Node Name: `http://frontend:8080/api/dashboard (category_id,date_from,date_to)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/loans
  * Node Name: `http://frontend:8080/api/loans`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/loans%3Fuser_id=&status=&overdue_only=false&q=&page=1&size=20
  * Node Name: `http://frontend:8080/api/loans (overdue_only,page,q,size,status,user_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/loans/10
  * Node Name: `http://frontend:8080/api/loans/10`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/loans/10/
  * Node Name: `http://frontend:8080/api/loans/10/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/loans/10/418843302132353612
  * Node Name: `http://frontend:8080/api/loans/10/418843302132353612`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/loans/5663817501870003344
  * Node Name: `http://frontend:8080/api/loans/5663817501870003344`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/maintenance
  * Node Name: `http://frontend:8080/api/maintenance`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/maintenance/
  * Node Name: `http://frontend:8080/api/maintenance/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/maintenance/728671670209012668
  * Node Name: `http://frontend:8080/api/maintenance/728671670209012668`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties
  * Node Name: `http://frontend:8080/api/penalties`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties%3Fuser_id=&status=&page=1&size=20
  * Node Name: `http://frontend:8080/api/penalties (page,size,status,user_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties/10
  * Node Name: `http://frontend:8080/api/penalties/10`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties/10/
  * Node Name: `http://frontend:8080/api/penalties/10/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties/10/2975606863546467585
  * Node Name: `http://frontend:8080/api/penalties/10/2975606863546467585`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties/8735590113454119678
  * Node Name: `http://frontend:8080/api/penalties/8735590113454119678`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations
  * Node Name: `http://frontend:8080/api/reservations`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations%3Fuser_id=&book_id=&status=&page=1&size=20
  * Node Name: `http://frontend:8080/api/reservations (book_id,page,size,status,user_id)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations/10
  * Node Name: `http://frontend:8080/api/reservations/10`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations/10/
  * Node Name: `http://frontend:8080/api/reservations/10/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations/10/2368786501090602123
  * Node Name: `http://frontend:8080/api/reservations/10/2368786501090602123`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations/9209004176609100932
  * Node Name: `http://frontend:8080/api/reservations/9209004176609100932`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/users
  * Node Name: `http://frontend:8080/api/users`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/users%3Fq=&role=&page=1&size=20
  * Node Name: `http://frontend:8080/api/users (page,q,role,size)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/users/10
  * Node Name: `http://frontend:8080/api/users/10`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/users/10/2614664534675526360
  * Node Name: `http://frontend:8080/api/users/10/2614664534675526360`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `404`
  * Other Info: ``
* URL: http://frontend:8080/api/users/6737647101717327389
  * Node Name: `http://frontend:8080/api/users/6737647101717327389`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/copies/10
  * Node Name: `http://frontend:8080/api/copies/10 ()({status})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/users/10
  * Node Name: `http://frontend:8080/api/users/10 ()({"full_name":"John Doe","role":"ADMIN","is_active":true,"password":ZAP})`
  * Method: `PATCH`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/login
  * Node Name: `http://frontend:8080/api/auth/login ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/login
  * Node Name: `http://frontend:8080/api/auth/login ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/register
  * Node Name: `http://frontend:8080/api/auth/register ()({email,full_name,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `409`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/register
  * Node Name: `http://frontend:8080/api/auth/register ()({email,full_name,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://frontend:8080/api/authors
  * Node Name: `http://frontend:8080/api/authors ()({full_name,nationality,birth_year})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books
  * Node Name: `http://frontend:8080/api/books ()({"isbn":"John Doe","title":"John Doe","publisher":"John Doe","publication_year":10,"summary":Zaproxy dolore alias impedit expedita quisquam.,"category_id":10,"author_ids":[10]})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://frontend:8080/api/books/10/copies
  * Node Name: `http://frontend:8080/api/books/10/copies ()({barcode,shelf_location})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/categories
  * Node Name: `http://frontend:8080/api/categories ()({"name":"ZAP","description":Zaproxy alias impedit expedita quisquam pariatur exercitationem. Nemo rerum eveniet dolores rem quia dignissimos.})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://frontend:8080/api/loans
  * Node Name: `http://frontend:8080/api/loans ()({user_id,barcode})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/loans/10/lost
  * Node Name: `http://frontend:8080/api/loans/10/lost`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/loans/10/renew
  * Node Name: `http://frontend:8080/api/loans/10/renew`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/loans/10/return
  * Node Name: `http://frontend:8080/api/loans/10/return`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/maintenance/run
  * Node Name: `http://frontend:8080/api/maintenance/run`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties
  * Node Name: `http://frontend:8080/api/penalties ()({user_id,amount,reason})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties/10/cancel
  * Node Name: `http://frontend:8080/api/penalties/10/cancel`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/penalties/10/pay
  * Node Name: `http://frontend:8080/api/penalties/10/pay`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations
  * Node Name: `http://frontend:8080/api/reservations ()({book_id,user_id})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/reservations/10/cancel
  * Node Name: `http://frontend:8080/api/reservations/10/cancel`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/users
  * Node Name: `http://frontend:8080/api/users ()({email,full_name,password,role})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/users/10/unlock
  * Node Name: `http://frontend:8080/api/users/10/unlock`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/computeMetadata/v1/
  * Node Name: `http://frontend:8080/computeMetadata/v1/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/latest/meta-data/
  * Node Name: `http://frontend:8080/latest/meta-data/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/metadata/instance
  * Node Name: `http://frontend:8080/metadata/instance ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/metadata/v1
  * Node Name: `http://frontend:8080/metadata/v1 ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/opc/v1/instance/
  * Node Name: `http://frontend:8080/opc/v1/instance/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/opc/v2/instance/
  * Node Name: `http://frontend:8080/opc/v2/instance/ ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/openstack/latest/meta_data.json
  * Node Name: `http://frontend:8080/openstack/latest/meta_data.json ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `405`
  * Other Info: ``
* URL: http://frontend:8080/api/authors/10
  * Node Name: `http://frontend:8080/api/authors/10 ()({full_name,nationality,birth_year})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `401`
  * Other Info: ``
* URL: http://frontend:8080/api/books/10
  * Node Name: `http://frontend:8080/api/books/10 ()({"isbn":"John Doe","title":"John Doe","publisher":"John Doe","publication_year":10,"summary":Zaproxy dolore alias impedit expedita quisquam.,"category_id":10,"author_ids":[10]})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``
* URL: http://frontend:8080/api/categories/10
  * Node Name: `http://frontend:8080/api/categories/10 ()({"name":"ZAP","description":Zaproxy alias impedit expedita quisquam pariatur exercitationem. Nemo rerum eveniet dolores rem quia dignissimos.})`
  * Method: `PUT`
  * Parameter: ``
  * Attack: ``
  * Evidence: `422`
  * Other Info: ``


Instances: 89

### Solution



### Reference



#### CWE Id: [ 388 ](https://cwe.mitre.org/data/definitions/388.html)


#### WASC Id: 20

#### Source ID: 4

### [ Authentication Request Identified ](https://www.zaproxy.org/docs/alerts/10111/)



##### Informational (High)

### Description

The given request has been identified as an authentication request. The 'Other Info' field contains a set of key=value lines which identify any relevant fields. If the request is in a context which has an Authentication Method set to "Auto-Detect" then this rule will change the authentication to match the request identified.

* URL: http://frontend:8080/api/users
  * Node Name: `http://frontend:8080/api/users ()({email,full_name,password,role})`
  * Method: `POST`
  * Parameter: `email`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=email
userValue=zaproxy@example.com
passwordParam=password`
* URL: http://frontend:8080/api/auth/login
  * Node Name: `http://frontend:8080/api/auth/login ()({email,password})`
  * Method: `POST`
  * Parameter: `email`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=email
userValue=zaproxy@example.com
passwordParam=password`


Instances: 2

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/)



#### Source ID: 3

### [ Information Disclosure - Sensitive Information in URL ](https://www.zaproxy.org/docs/alerts/10024/)



##### Informational (Medium)

### Description

The request appeared to contain sensitive information leaked in the URL. This can violate PCI and most organizational compliance policies. You can configure the list of strings for this check to add or remove values specific to your environment.

* URL: http://frontend:8080/api/audit%3Faction=&entity_type=&user_email=&date_from=&date_to=&page=1&size=50
  * Node Name: `http://frontend:8080/api/audit (action,date_from,date_to,entity_type,page,size,user_email)`
  * Method: `GET`
  * Parameter: `user_email`
  * Attack: ``
  * Evidence: `user_email`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: user
user_email`
* URL: http://frontend:8080/api/loans%3Fuser_id=&status=&overdue_only=false&q=&page=1&size=20
  * Node Name: `http://frontend:8080/api/loans (overdue_only,page,q,size,status,user_id)`
  * Method: `GET`
  * Parameter: `user_id`
  * Attack: ``
  * Evidence: `user_id`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: user
user_id`
* URL: http://frontend:8080/api/penalties%3Fuser_id=&status=&page=1&size=20
  * Node Name: `http://frontend:8080/api/penalties (page,size,status,user_id)`
  * Method: `GET`
  * Parameter: `user_id`
  * Attack: ``
  * Evidence: `user_id`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: user
user_id`
* URL: http://frontend:8080/api/reservations%3Fuser_id=&book_id=&status=&page=1&size=20
  * Node Name: `http://frontend:8080/api/reservations (book_id,page,size,status,user_id)`
  * Method: `GET`
  * Parameter: `user_id`
  * Attack: ``
  * Evidence: `user_id`
  * Other Info: `The URL contains potentially sensitive information. The following string was found via the pattern: user
user_id`


Instances: 4

### Solution

Do not pass sensitive information in URIs.

### Reference



#### CWE Id: [ 598 ](https://cwe.mitre.org/data/definitions/598.html)


#### WASC Id: 13

#### Source ID: 3

### [ Non-Storable Content ](https://www.zaproxy.org/docs/alerts/10049/)



##### Informational (Medium)

### Description

The response contents are not storable by caching components such as proxy servers. If the response does not contain sensitive, personal or user-specific information, it may benefit from being stored and cached, to improve performance.

* URL: http://frontend:8080/api/auth/me
  * Node Name: `http://frontend:8080/api/auth/me`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `no-store`
  * Other Info: ``
* URL: http://frontend:8080/api/users%3Fq=&role=&page=1&size=20
  * Node Name: `http://frontend:8080/api/users (page,q,role,size)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `no-store`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/login
  * Node Name: `http://frontend:8080/api/auth/login ()({email,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `no-store`
  * Other Info: ``
* URL: http://frontend:8080/api/auth/register
  * Node Name: `http://frontend:8080/api/auth/register ()({email,full_name,password})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `no-store`
  * Other Info: ``
* URL: http://frontend:8080/api/users
  * Node Name: `http://frontend:8080/api/users ()({email,full_name,password,role})`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `no-store`
  * Other Info: ``

Instances: Systemic


### Solution

The content may be marked as storable by ensuring that the following conditions are satisfied:
The request method must be understood by the cache and defined as being cacheable ("GET", "HEAD", and "POST" are currently defined as cacheable)
The response status code must be understood by the cache (one of the 1XX, 2XX, 3XX, 4XX, or 5XX response classes are generally understood)
The "no-store" cache directive must not appear in the request or response header fields
For caching by "shared" caches such as "proxy" caches, the "private" response directive must not appear in the response
For caching by "shared" caches such as "proxy" caches, the "Authorization" header field must not appear in the request, unless the response explicitly allows it (using one of the "must-revalidate", "public", or "s-maxage" Cache-Control response directives)
In addition to the conditions above, at least one of the following conditions must also be satisfied by the response:
It must contain an "Expires" header field
It must contain a "max-age" response directive
For "shared" caches such as "proxy" caches, it must contain a "s-maxage" response directive
It must contain a "Cache Control Extension" that allows it to be cached
It must have a status code that is defined as cacheable by default (200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501).

### Reference


* [ https://datatracker.ietf.org/doc/html/rfc7234 ](https://datatracker.ietf.org/doc/html/rfc7234)
* [ https://datatracker.ietf.org/doc/html/rfc7231 ](https://datatracker.ietf.org/doc/html/rfc7231)
* [ https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html ](https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html)


#### CWE Id: [ 524 ](https://cwe.mitre.org/data/definitions/524.html)


#### WASC Id: 13

#### Source ID: 3


