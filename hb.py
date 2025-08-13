
import json
import logging
import re
from pathlib import Path

import requests


ROOT = Path(__file__).parent
ASSETS = ROOT / 'assets'
logging.getLogger(__name__)


# inconsistencies in naming
NAME_EXCEPTIONS = {
    'hackerbox-0095-ai-camera-lab': 'hackerbox-0095-ai-camera',
    'hackerbox-0050-fifty': 'hackerbox-0050',
    'hackerbox-0039-level-up': 'hackerbox-0039-power-up',
    'hackerbox-0022-bbc-microbit': 'hackerbox-0022-bbc-micro-bit'
}


class HackerBoxes:
    """Retrieve HackerBox information."""

    def __init__(self):
        self.session = requests.session()
        self.url = 'https://hackerboxes.com/collections/past-hackerboxes'

    def parse_box_names(self, url: str) -> list[str]:
        """Parse only the relevant details of a box."""
        response = self.session.get(url)
        response.raise_for_status()
        match = re.search(r'var meta = (?P<products>{"products":.+?});\n', response.text, re.DOTALL)
        assert match and match.group('products'), f'no products found for: {url}!'
        products = json.loads(match.group('products'))['products']
        assert products

        names = []
        for product in products:
            raw_product = product['variants'][0]['name'][11:]  # len(HackerBox #) = 11
            number, raw_name = raw_product.split(' - ', 1)
            number = number.strip()

            if ' - ' in raw_name:
                raw_name = raw_name.split(' - ', 1)[0]
            if not raw_name.isalnum():
                raw_name = re.sub(r'[^a-zA-Z0-9\s-]', '', raw_name)

            name = '-'.join(raw_name.split()).lower()
            full_name = f'hackerbox-{number}-{name}'
            if full_name in NAME_EXCEPTIONS:
                full_name = NAME_EXCEPTIONS[full_name]
            names.append(full_name)

        return names

    def get_all_boxes(self) -> list[str]:
        """Retrieve all released boxes."""
        boxes = self.parse_box_names(self.url)
        i = 2
        while True:
            try:
                names = self.parse_box_names(f'{self.url}?page={i}')
                boxes.extend(names)
                i += 1
            except (requests.HTTPError, AssertionError):
                break

        return boxes

    def get_box_contents(self, name: str) -> (dict, dict):
        """Get the picture and contents of a box for a table and for json dump."""
        box_url = f'{self.url}/products/{name}'
        response = self.session.get(box_url)
        match = re.search(r'ProductJson-product-template">\s+(?P<product>{.+?})\n\s+</script>\s', response.text, re.DOTALL)
        assert match and match.group('product'), f'no contents json found for: {name}!'
        product = json.loads(match.group('product'))
        description = product['description']
        assert description

        contents = re.findall(r'\n<li.*?>(.+?)<\\?/li>\n', description)
        image_url = product['featured_image'][2:]
        image_response = requests.get(f'https://{image_url}')
        image = image_response.content
        image_path = ASSETS / f'{name}.png'
        image_path.write_bytes(image)
        print(f'File written to: {image_path}')

        # <ul><li>Sub-item 1</li><li>Sub-item 2</li></ul>
        bullets = [f'<li>{b}</li>' for b in contents]
        table_contents = f'<ul>{"".join(bullets)}</ul>'
        table_name = f'[{name}]({box_url})'

        table_data = {'name': table_name, 'picture': f'![{name}](assets/{image_path.name})', 'contents': table_contents}
        json_data = {'name': name, 'picture': f'![{name}](assets/{image_path.name})', 'contents': contents}
        return table_data, json_data

    def get_all_box_contents(self) -> (list[dict], list[dict]):
        """Get contents for all boxes."""
        table_contents = []
        json_contents = []
        for name in self.get_all_boxes():
            t, j = self.get_box_contents(name)
            table_contents.append(t)
            json_contents.append(j)
        return table_contents, json_contents


class MarkdownTable:
    """Generate a markdown table."""

    def __init__(self, headers: list[str], rows: list[dict]):
        for row in rows:
            assert all(h in row for h in headers), f'Missing header for: {row}'
        self.headers = headers
        self.rows = rows

    def make_headers(self) -> str:
        """Setup headers."""
        header = '| ' + ' | '.join(self.headers).strip() + ' |\n'
        column_lengths = [len(h) + 2 for h in self.headers]
        header += '| ' + ' | '.join(['-' * cl for cl in column_lengths]) + ' |\n'
        return header

    def make_rows(self) -> str:
        """Create rows."""
        all_rows = ''
        rows = [[row[h] for h in self.headers] for row in self.rows]
        for row in rows:
            all_rows += '| ' + ' | '.join(row) + ' |\n'

        return all_rows

    def generate(self) -> str:
        """Generate the table."""
        generated = self.make_headers()
        generated += self.make_rows()
        return generated


if __name__ == '__main__':
    hb = HackerBoxes()
    contents_t, contents_d = hb.get_all_box_contents()
    table = MarkdownTable(['name', 'picture', 'contents'], contents_t)
    print(table.generate())
    print(json.dumps(contents_d, indent=2))
