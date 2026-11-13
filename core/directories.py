# Copyright 2017 Virgil Dupras
#
# This software is licensed under the "GPLv3" License as described in the "LICENSE" file,
# which should be included with this package. The terms are also available at
# http://www.gnu.org/licenses/gpl-3.0.html

import os
from xml.etree import ElementTree as ET
import logging
from pathlib import Path

from hscommon.jobprogress import job
from hscommon.util import FileOrPath
from hscommon.trans import tr

from core import fs

__all__ = [
    "Directories",
    "DirectoryState",
    "AlreadyThereError",
    "InvalidPathError",
]


class DirectoryState:
    """Enum describing how a folder should be considered.

    * DirectoryState.Normal: Scan all files normally
    * DirectoryState.Reference: Scan files, but make sure never to delete any of them
    * DirectoryState.Excluded: Don't scan this folder
    """

    NORMAL = 0
    REFERENCE = 1
    EXCLUDED = 2


class AlreadyThereError(Exception):
    """The path being added is already in the directory list"""


class InvalidPathError(Exception):
    """The path being added is invalid"""


def _path_key(path):
    # String form that compares like ``Path`` equality (case-insensitive on Windows).
    return os.path.normcase(str(path))


def _is_within(key, ancestor_key):
    """Whether ``key`` is ``ancestor_key`` or below it. Both come from :func:`_path_key`."""
    return key == ancestor_key or key.startswith(os.path.join(ancestor_key, ""))


class Directories:
    """Holds user folder selection.

    Manages the selection that the user make through the folder selection dialog. It also manages
    folder states, and how recursion applies to them.

    Then, when the user starts the scan, :meth:`get_files` is called to retrieve all files (wrapped
    in :mod:`core.fs`) that have to be scanned according to the chosen folders/states.
    """

    # ---Override
    def __init__(self, exclude_list=None):
        self._dirs = []
        # {path: state}
        self.states = {}
        self._exclude_list = exclude_list

    def __contains__(self, path):
        for p in self._dirs:
            if path == p or p in path.parents:
                return True
        return False

    def __delitem__(self, key):
        self._dirs.__delitem__(key)

    def __getitem__(self, key):
        return self._dirs.__getitem__(key)

    def __len__(self):
        return len(self._dirs)

    # ---Private
    def _default_state_for_path(self, path):
        # New logic with regex filters
        if self._exclude_list is not None and self._exclude_list.mark_count > 0:
            # We iterate even if we only have one item here
            for denied_path_re in self._exclude_list.compiled:
                if denied_path_re.match(str(path.name)):
                    return DirectoryState.EXCLUDED
            return DirectoryState.NORMAL
        # Override this in subclasses to specify the state of some special folders.
        if path.name.startswith("."):
            return DirectoryState.EXCLUDED
        return DirectoryState.NORMAL

    @staticmethod
    def _first_visit(path, visited):
        """Records the real folder behind ``path`` in ``visited`` and returns whether it's new.

        A symlink or junction can point back to one of its ancestors (a folder loop) or to a
        folder that is also reachable through another path. Walking it again would make the scan
        go around the loop until paths get too long, and yield the same files under different
        paths, which would then be reported as duplicates of themselves.
        """
        key = fs.folder_key(path)
        if key is None:
            return True
        if key in visited:
            logging.debug("Skipping already visited folder %s", str(path))
            return False
        visited.add(key)
        return True

    def _get_files(self, from_path, fileclasses, j, visited):
        if not self._first_visit(from_path, visited):
            return
        try:
            with os.scandir(from_path) as iter:
                root_path = Path(from_path)
                state = self.get_state(root_path)
                # if we have no un-excluded dirs under this directory skip going deeper
                skip_dirs = state == DirectoryState.EXCLUDED and not any(
                    p.parts[: len(root_path.parts)] == root_path.parts for p in self.states
                )
                count = 0
                for item in iter:
                    j.check_if_cancelled()
                    try:
                        if item.is_dir():
                            if skip_dirs:
                                continue
                            yield from self._get_files(item.path, fileclasses, j, visited)
                            continue
                        elif state == DirectoryState.EXCLUDED:
                            continue
                        # File excluding or not
                        if (
                            self._exclude_list is None
                            or not self._exclude_list.mark_count
                            or not self._exclude_list.is_excluded(str(from_path), item.name)
                        ):
                            file = fs.get_file(item, fileclasses=fileclasses)
                            if file:
                                file.is_ref = state == DirectoryState.REFERENCE
                                count += 1
                                yield file
                    except (OSError, fs.InvalidPath):
                        pass
                logging.debug(
                    "Collected %d files in folder %s",
                    count,
                    str(root_path),
                )
        except OSError:
            pass

    def _get_folders(self, from_folder, j, visited):
        j.check_if_cancelled()
        if not self._first_visit(from_folder.path, visited):
            return
        try:
            for subfolder in from_folder.subfolders:
                yield from self._get_folders(subfolder, j, visited)
            state = self.get_state(from_folder.path)
            if state != DirectoryState.EXCLUDED:
                from_folder.is_ref = state == DirectoryState.REFERENCE
                logging.debug("Yielding Folder %r state: %d", from_folder, state)
                yield from_folder
        except (OSError, fs.InvalidPath):
            pass

    # ---Public
    def add_path(self, path):
        """Adds ``path`` to self, if not already there.

        Raises :exc:`AlreadyThereError` if ``path`` is already in self. If path is a directory
        containing some of the directories already present in self, ``path`` will be added, but all
        directories under it will be removed. Can also raise :exc:`InvalidPathError` if ``path``
        does not exist.

        :param Path path: path to add
        """
        if path in self:
            raise AlreadyThereError()
        if not path.exists():
            raise InvalidPathError()
        self._dirs = [p for p in self._dirs if path not in p.parents]
        self._dirs.append(path)

    @staticmethod
    def get_subfolders(path):
        """Returns a sorted list of paths corresponding to subfolders in ``path``.

        :param Path path: get subfolders from there
        :rtype: list of Path
        """
        try:
            # scandir knows each entry's type from the directory listing, so unlike
            # glob() + is_dir() it doesn't need a separate stat call for every file.
            with os.scandir(path) as entries:
                subpaths = [Path(entry.path) for entry in entries if entry.is_dir()]
        except OSError:
            return []
        subpaths.sort(key=lambda x: x.name.lower())
        return subpaths

    def get_files(self, fileclasses=None, j=job.nulljob):
        """Returns a list of all files that are not excluded.

        Returned files also have their ``is_ref`` attr set if applicable.
        """
        if fileclasses is None:
            fileclasses = [fs.File]
        file_count = 0
        visited = set()
        for path in self._dirs:
            for file in self._get_files(path, fileclasses=fileclasses, j=j, visited=visited):
                file_count += 1
                if not isinstance(j, job.NullJob):
                    j.set_progress(-1, tr("Collected {} files to scan").format(file_count))
                yield file

    def get_folders(self, folderclass=None, j=job.nulljob):
        """Returns a list of all folders that are not excluded.

        Returned folders also have their ``is_ref`` attr set if applicable.
        """
        if folderclass is None:
            folderclass = fs.Folder
        folder_count = 0
        visited = set()
        for path in self._dirs:
            from_folder = folderclass(path)
            for folder in self._get_folders(from_folder, j, visited):
                folder_count += 1
                if not isinstance(j, job.NullJob):
                    j.set_progress(-1, tr("Collected {} folders to scan").format(folder_count))
                yield folder

    def get_state(self, path):
        """Returns the state of ``path``.

        :rtype: :class:`DirectoryState`
        """
        # direct match? easy result.
        if path in self.states:
            return self.states[path]
        state = self._default_state_for_path(path)
        # Save non-default states in cache, necessary for _get_files()
        if state != DirectoryState.NORMAL:
            self.states[path] = state
            return state
        # Inherit from the nearest parent that has a state, or that is excluded by default (a
        # hidden folder or one matching an exclusion rule). Default exclusions only apply from the
        # selected root folder down: a root added inside a hidden folder is still scanned.
        # NOTE: path.parents is ordered longest to shortest
        root_depth = self._containing_root_depth(path)
        depth = len(path.parts)
        for parent_path in path.parents:
            depth -= 1
            if parent_path in self.states:
                return self.states[parent_path]
            if (
                root_depth is not None
                and depth >= root_depth
                and self._default_state_for_path(parent_path) == DirectoryState.EXCLUDED
            ):
                return DirectoryState.EXCLUDED
        return state

    def _containing_root_depth(self, path):
        """Number of path parts of the selected root folder containing ``path``, or None."""
        key = _path_key(path)
        depths = [len(root.parts) for root in self._dirs if _is_within(key, _path_key(root))]
        return max(depths, default=None)

    def has_any_file(self):
        """Returns whether selected folders contain any file.

        Because it stops at the first file it finds, it's much faster than get_files().

        :rtype: bool
        """
        try:
            next(self.get_files())
            return True
        except StopIteration:
            return False

    def load_from_file(self, infile):
        """Load folder selection from ``infile``.

        :param file infile: path or file pointer to XML generated through :meth:`save_to_file`
        """
        try:
            root = ET.parse(infile).getroot()
        except Exception:
            return
        for rdn in root.iter("root_directory"):
            attrib = rdn.attrib
            if "path" not in attrib:
                continue
            path = attrib["path"]
            try:
                self.add_path(Path(path))
            except (AlreadyThereError, InvalidPathError):
                pass
        for sn in root.iter("state"):
            attrib = sn.attrib
            if not ("path" in attrib and "value" in attrib):
                continue
            path = attrib["path"]
            state = attrib["value"]
            self.states[Path(path)] = int(state)

    def save_to_file(self, outfile):
        """Save folder selection as XML to ``outfile``.

        :param file outfile: path or file pointer to XML file to save to.
        """
        with FileOrPath(outfile, "wb") as fp:
            root = ET.Element("directories")
            for root_path in self:
                root_path_node = ET.SubElement(root, "root_directory")
                root_path_node.set("path", str(root_path))
            for path, state in self.states.items():
                if state == DirectoryState.EXCLUDED and self._default_state_for_path(path) == state:
                    # Only a cached default (hidden folder or exclusion rule match); get_state()
                    # recomputes it. Saving these made the file grow with every scan.
                    continue
                state_node = ET.SubElement(root, "state")
                state_node.set("path", str(path))
                state_node.set("value", str(state))
            tree = ET.ElementTree(root)
            tree.write(fp, encoding="utf-8")

    def set_state(self, path, state):
        """Set the state of folder at ``path``.

        :param Path path: path of the target folder
        :param state: state to set folder to
        :type state: :class:`DirectoryState`
        """
        if self.get_state(path) == state:
            return
        # Drop states of subfolders: they now inherit the new state. A string prefix check is
        # used because ``path in p.parents`` builds every parent of every state, which took
        # seconds with thousands of deep states.
        prefix = os.path.join(_path_key(path), "")
        for iter_path in list(self.states.keys()):
            if _path_key(iter_path).startswith(prefix):
                del self.states[iter_path]
        self.states[path] = state
