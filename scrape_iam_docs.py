#!/usr/bin/env python3

import requests
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def main():

    for service, page in process_main_page():
        print(service)
        service_prefix, actions = process_action_page(page)
        service_actions = reduce_actions(actions)

        with open(f"services/{service_prefix}.json", "w") as file:
            json.dump({
                'service': service,
                'prefix': service_prefix,
                'actions': service_actions
            }, file, indent=4, sort_keys=True)


def process_main_page():
    base_url = 'https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_actions-resources-contextkeys.html'
    resp = requests.get(base_url)

    soup = BeautifulSoup(resp.text, 'html.parser')

    list_of_pages = soup.find("div", class_="highlights").find("ul")

    for item in list_of_pages.find_all("a"):
        service_page = urljoin(base_url, item['href'])
        yield item.get_text(), service_page


def process_action_page(page_url):
    resp = requests.get(page_url)

    soup = BeautifulSoup(resp.text, 'html.parser')

    service_short = soup.find('div', id="main-col-body").find("code").get_text()

    actions = []

    for table in soup.find_all('table'):
        headers = [th.get_text() for th in table.thead.find_all('th')]

        if "Actions" in headers:
            actions = list(process_table(table, headers))
        else:
            print('unknown table', headers)

    return service_short, actions


def process_table(table, headers):
    rowspans = [(0, None) for _ in headers]

    # [1:] to skip the header row
    for row in table.find_all('tr')[1:]:
        row = row.find_all('td')

        rowspans, row_items = merge_rowspan_with_row(rowspans, row)

        row_dict = dict(zip(headers, row_items))

        yield row_dict


def merge_rowspan_with_row(rowspans, row):
    # handle rowspan='n' cases
    item_diff = len(rowspans) - len(row)

    if item_diff > 0:
        # pad out the row
        row = [None for _ in range(0, item_diff)] + row

    new_rowspan = []
    row_result = []
    for rowspan, item in zip(rowspans, row):
        span_count, span_value = rowspan

        if span_count <= 0:
            span = int(item.get('rowspan', '1'))
            result = item.get_text().strip()
            new_rowspan.append((span - 1, result))
            row_result.append(result)
        else:
            new_rowspan.append((span_count - 1, span_value))
            row_result.append(span_value)

    return new_rowspan, row_result


def reduce_actions(service_actions):
    actions = {}

    for service_action in service_actions:
        action_name_split = service_action['Actions'].split()
        action_name = action_name_split[0]
        permission_only = len(action_name_split) > 1

        description = " ".join(service_action['Description'].split())

        access_level = service_action['Access level']
        # TODO handle required resoures
        resources_bare = service_action['Resource types (*required)'].split()

        resources = []
        for r in resources_bare:
            resources.append({
                "name": r.strip('*'),
                "required": r.endswith('*')
            })

        condition_keys = service_action['Condition keys'].split()

        dependent_actions = service_action['Dependent actions'].split()

        action = actions.get(action_name, {
            'action': action_name,
            'description': description,
            'access_level': access_level,
            'permission_only':  permission_only,
            'resources': [],
            'condition_keys': [],
            'dependent_actions': []
        })

        action['resources'].extend(resources)
        action['condition_keys'].extend(condition_keys)
        action['dependent_actions'].extend(dependent_actions)

        actions[action_name] = action

    return list(actions.values())


if __name__ == '__main__':
    main()
