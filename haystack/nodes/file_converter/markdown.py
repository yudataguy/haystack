import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    import frontmatter
    from bs4 import BeautifulSoup, NavigableString
    from markdown import markdown
except (ImportError, ModuleNotFoundError) as ie:
    from haystack.utils.import_utils import _optional_component_not_installed

    _optional_component_not_installed(__name__, "file-conversion", ie)

from haystack.nodes.file_converter.base import BaseConverter
from haystack.schema import Document


logger = logging.getLogger(__name__)


class MarkdownConverter(BaseConverter):
    def __init__(
        self,
        remove_numeric_tables: bool = False,
        valid_languages: Optional[List[str]] = None,
        id_hash_keys: Optional[List[str]] = None,
        progress_bar: bool = True,
        remove_code_snippets: bool = True,
        extract_headlines: bool = False,
        add_frontmatter_to_meta: bool = False,
    ):
        """
        :param remove_numeric_tables: Not applicable.
        :param valid_languages: Not applicable.
        :param id_hash_keys: Generate the document ID from a custom list of strings that refer to the document's
            attributes. To make sure you don't have duplicate documents in your DocumentStore if texts are
            not unique, you can modify the metadata and pass for example, `"meta"` to this field ([`"content"`, `"meta"`]).
            In this case, the ID is generated by using the content and the defined metadata.
        :param progress_bar: Show a progress bar for the conversion.
        :param remove_code_snippets: Whether to remove snippets from the markdown file.
        :param extract_headlines: Whether to extract headings from the markdown file.
        :param add_frontmatter_to_meta: Whether to add the contents of the frontmatter to `meta`.
        """
        super().__init__(
            remove_numeric_tables=remove_numeric_tables,
            valid_languages=valid_languages,
            id_hash_keys=id_hash_keys,
            progress_bar=progress_bar,
        )

        self.remove_code_snippets = remove_code_snippets
        self.extract_headlines = extract_headlines
        self.add_frontmatter_to_meta = add_frontmatter_to_meta

    def convert(
        self,
        file_path: Path,
        meta: Optional[Dict[str, Any]] = None,
        remove_numeric_tables: Optional[bool] = None,
        valid_languages: Optional[List[str]] = None,
        encoding: Optional[str] = "utf-8",
        id_hash_keys: Optional[List[str]] = None,
        remove_code_snippets: Optional[bool] = None,
        extract_headlines: Optional[bool] = None,
        add_frontmatter_to_meta: Optional[bool] = None,
    ) -> List[Document]:
        """
        Reads text from a markdown file and executes optional preprocessing steps.

        :param file_path: path of the file to convert
        :param meta: dictionary of meta data key-value pairs to append in the returned document.
        :param encoding: Select the file encoding (default is `utf-8`)
        :param remove_numeric_tables: Not applicable
        :param valid_languages: Not applicable
        :param id_hash_keys: Generate the document id from a custom list of strings that refer to the document's
            attributes. If you want to ensure you don't have duplicate documents in your DocumentStore but texts are
            not unique, you can modify the metadata and pass e.g. `"meta"` to this field (e.g. [`"content"`, `"meta"`]).
            In this case the id will be generated by using the content and the defined metadata.
        :param remove_code_snippets: Whether to remove snippets from the markdown file.
        :param extract_headlines: Whether to extract headings from the markdown file.
        :param add_frontmatter_to_meta: Whether to add the contents of the frontmatter to `meta`.
        """

        id_hash_keys = id_hash_keys if id_hash_keys is not None else self.id_hash_keys
        remove_code_snippets = remove_code_snippets if remove_code_snippets is not None else self.remove_code_snippets
        extract_headlines = extract_headlines if extract_headlines is not None else self.extract_headlines
        add_frontmatter_to_meta = (
            add_frontmatter_to_meta if add_frontmatter_to_meta is not None else self.add_frontmatter_to_meta
        )

        with open(file_path, encoding=encoding, errors="ignore") as f:
            metadata, markdown_text = frontmatter.parse(f.read())

        # md -> html -> text since BeautifulSoup can extract text cleanly
        html = markdown(markdown_text, extensions=["fenced_code"])

        # remove code snippets
        if remove_code_snippets:
            html = re.sub(r"<pre>(.*?)</pre>", " ", html, flags=re.DOTALL)
            html = re.sub(r"<code>(.*?)</code>", " ", html, flags=re.DOTALL)
        soup = BeautifulSoup(html, "html.parser")

        if add_frontmatter_to_meta:
            if meta is None:
                meta = metadata
            else:
                meta.update(metadata)

        if extract_headlines:
            text, headlines = self._extract_text_and_headlines(soup)
            if meta is None:
                meta = {}
            meta["headlines"] = headlines
        else:
            text = soup.get_text()

        if meta is None:
            meta = {"filename": file_path.name}
        else:
            meta["filename"] = file_path.name

        document = Document(content=text, meta=meta, id_hash_keys=id_hash_keys)
        return [document]

    @staticmethod
    def _extract_text_and_headlines(soup: BeautifulSoup) -> Tuple[str, List[Dict]]:
        """
        Extracts text and headings from a soup object.
        """
        headline_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        headlines = []
        text = ""
        for desc in soup.descendants:
            if desc.name in headline_tags:
                current_headline = desc.get_text()
                current_start_idx = len(text)
                current_level = int(desc.name[-1]) - 1
                headlines.append({"headline": current_headline, "start_idx": current_start_idx, "level": current_level})

            if isinstance(desc, NavigableString):
                text += desc.get_text()

        return text, headlines
