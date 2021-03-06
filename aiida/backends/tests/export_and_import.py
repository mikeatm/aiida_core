# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida_core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""
Tests for the export and import routines.
"""

from aiida.backends.testbase import AiidaTestCase
from aiida.orm.importexport import import_data


class TestSpecificImport(AiidaTestCase):

    def setUp(self):
        super(TestSpecificImport, self).setUp()
        self.clean_db()
        self.insert_data()

    def test_simple_import(self):
        """
        This is a very simple test which checks that an export file with nodes
        that are not associated to a computer is imported correctly. In Django
        when such nodes are exported, there is an empty set for computers
        in the export file. In SQLA there is such a set only when a computer is
        associated with the exported nodes. When an empty computer set is
        found at the export file (when imported to an SQLA profile), the SQLA
        import code used to crash. This test demonstrates this problem.
        """
        import tempfile
        from aiida.orm.data.parameter import ParameterData
        from aiida.orm.importexport import export, import_data
        from aiida.orm.node import Node
        from aiida.orm.querybuilder import QueryBuilder

        parameters = ParameterData(dict={
            'Pr': {
                'cutoff': 50.0,
                'pseudo_type': 'Wentzcovitch',
                'dual': 8,
                'cutoff_units': 'Ry'
            },
            'Ru': {
                'cutoff': 40.0,
                'pseudo_type': 'SG15',
                'dual': 4,
                'cutoff_units': 'Ry'
            },
        }).store()

        with tempfile.NamedTemporaryFile() as handle:

            nodes = [parameters.dbnode]
            export(nodes, outfile=handle.name, overwrite=True, silent=True)

            # Check that we have the expected number of nodes in the database
            self.assertEquals(QueryBuilder().append(Node).count(), len(nodes))

            # Clean the database and verify there are no nodes left
            self.clean_db()
            self.assertEquals(QueryBuilder().append(Node).count(), 0)

            # After importing we should have the original number of nodes again
            import_data(handle.name, silent=True)
            self.assertEquals(QueryBuilder().append(Node).count(), len(nodes))

    def test_cycle_structure_data(self):
        """
        Create an export with some Calculation and Data nodes and import it after having
        cleaned the database. Verify that the nodes and their attributes are restored
        properly after importing the created export archive
        """
        import tempfile
        from aiida.common.links import LinkType
        from aiida.orm.calculation import Calculation
        from aiida.orm.data.structure import StructureData
        from aiida.orm.data.remote import RemoteData
        from aiida.orm.importexport import export, import_data
        from aiida.orm.node import Node
        from aiida.orm.querybuilder import QueryBuilder

        test_label = 'Test structure'
        test_cell = [
            [8.34, 0.0, 0.0],
            [0.298041701839357, 8.53479766274308, 0.0],
            [0.842650688117053, 0.47118495164127, 10.6965192730702]
        ]
        test_kinds = [
            {
                'symbols': [u'Fe'],
                'weights': [1.0],
                'mass': 55.845,
                'name': u'Fe'
            },
            {
                'symbols': [u'S'],
                'weights': [1.0],
                'mass': 32.065,
                'name': u'S'
            }
        ]

        structure = StructureData(cell=test_cell)
        structure.append_atom(symbols=['Fe'], position=[0, 0, 0])
        structure.append_atom(symbols=['S'], position=[2, 2, 2])
        structure.label = test_label
        structure.store()

        parent_calculation = Calculation()
        parent_calculation._set_attr('key', 'value')
        parent_calculation.store()
        child_calculation = Calculation()
        child_calculation._set_attr('key', 'value')
        child_calculation.store()
        remote_folder = RemoteData(computer=self.computer, remote_path='/').store()

        remote_folder.add_link_from(parent_calculation, link_type=LinkType.CREATE)
        child_calculation.add_link_from(remote_folder, link_type=LinkType.INPUT)
        structure.add_link_from(child_calculation, link_type=LinkType.CREATE)

        with tempfile.NamedTemporaryFile() as handle:

            nodes = [structure.dbnode, child_calculation.dbnode, parent_calculation.dbnode, remote_folder.dbnode]
            export(nodes, outfile=handle.name, overwrite=True, silent=True)

            # Check that we have the expected number of nodes in the database
            self.assertEquals(QueryBuilder().append(Node).count(), len(nodes))

            # Clean the database and verify there are no nodes left
            self.clean_db()
            self.assertEquals(QueryBuilder().append(Node).count(), 0)

            # After importing we should have the original number of nodes again
            import_data(handle.name, silent=True)
            self.assertEquals(QueryBuilder().append(Node).count(), len(nodes))

            # Verify that Calculations have non-empty attribute dictionaries
            qb = QueryBuilder().append(Calculation)
            for [calculation] in qb.iterall():
                self.assertIsInstance(calculation.get_attrs(), dict)
                self.assertNotEquals(len(calculation.get_attrs()), 0)

            # Verify that the structure data maintained its label, cell and kinds
            qb = QueryBuilder().append(StructureData)
            for [structure] in qb.iterall():
                self.assertEquals(structure.label, test_label)
                self.assertEquals(structure.cell, test_cell)

            qb = QueryBuilder().append(StructureData, project=['attributes.kinds'])
            for [kinds] in qb.iterall():
                self.assertEqual(len(kinds), 2)
                for kind in kinds:
                    self.assertIn(kind, test_kinds)

            # Check that there is a StructureData that is an output of a Calculation
            qb = QueryBuilder()
            qb.append(Calculation, project=['uuid'], tag='calculation')
            qb.append(StructureData, output_of='calculation')
            self.assertGreater(len(qb.all()), 0)

            # Check that there is a RemoteData that is a child and parent of a Calculation
            qb = QueryBuilder()
            qb.append(Calculation, tag='parent')
            qb.append(RemoteData, project=['uuid'], output_of='parent', tag='remote')
            qb.append(Calculation, output_of='remote')
            self.assertGreater(len(qb.all()), 0)


class TestSimple(AiidaTestCase):

    def setUp(self):
        self.clean_db()
        self.insert_data()

    def tearDown(self):
        pass

    def test_0(self):
        import os
        import shutil
        import tempfile

        from aiida.orm import DataFactory
        from aiida.orm import load_node
        from aiida.orm.data.bool import Bool
        from aiida.orm.data.float import Float
        from aiida.orm.data.int import Int
        from aiida.orm.data.str import Str
        from aiida.orm.calculation.job import JobCalculation
        from aiida.orm.importexport import export

        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()
        try:
            # producing values for each base type
            values = ("Hello", 6, -1.2399834e12, False)  # , ["Bla", 1, 1e-10])
            filename = os.path.join(temp_folder, "export.tar.gz")

            # producing nodes:
            nodes = [cls(val).store() for val, cls in zip(values, (Str, Int, Float, Bool))]
            # my uuid - list to reload the node:
            uuids = [n.uuid for n in nodes]
            # exporting the nodes:
            export([n.dbnode for n in nodes], outfile=filename, silent=True)
            # cleaning:
            self.clean_db()
            # Importing back the data:
            import_data(filename, silent=True)
            # Checking whether values are preserved:
            for uuid, refval in zip(uuids, values):
                self.assertEquals(load_node(uuid).value, refval)
        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)

    def test_1(self):
        import os
        import shutil
        import tempfile

        from aiida.orm import DataFactory
        from aiida.orm import load_node
        from aiida.orm.calculation.job import JobCalculation
        from aiida.orm.importexport import export

        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()
        try:
            StructureData = DataFactory('structure')
            sd = StructureData()
            sd.store()

            calc = JobCalculation()
            calc.set_computer(self.computer)
            calc.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            calc.store()

            calc.add_link_from(sd)

            pks = [sd.pk, calc.pk]

            attrs = {}
            for pk in pks:
                node = load_node(pk)
                attrs[node.uuid] = dict()
                for k in node.attrs():
                    attrs[node.uuid][k] = node.get_attr(k)

            filename = os.path.join(temp_folder, "export.tar.gz")

            export([calc.dbnode], outfile=filename, silent=True)

            self.clean_db()

            # NOTE: it is better to load new nodes by uuid, rather than assuming
            # that they will have the first 3 pks. In fact, a recommended policy in
            # databases is that pk always increment, even if you've deleted elements
            import_data(filename, silent=True)
            for uuid in attrs.keys():
                node = load_node(uuid)
                # for k in node.attrs():
                for k in attrs[uuid].keys():
                    self.assertEquals(attrs[uuid][k], node.get_attr(k))
        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)
            # print temp_folder

    def test_2(self):
        """
        Test the check for the export format version.
        """
        import json
        import tarfile
        import os
        import shutil
        import tempfile

        from aiida.orm import DataFactory
        from aiida.orm.importexport import export

        # Creating a folder for the import/export files
        export_file_tmp_folder = tempfile.mkdtemp()
        unpack_tmp_folder = tempfile.mkdtemp()
        try:
            StructureData = DataFactory('structure')
            sd = StructureData()
            sd.store()

            filename = os.path.join(export_file_tmp_folder, "export.tar.gz")
            export([sd.dbnode], outfile=filename, silent=True)

            with tarfile.open(filename, "r:gz", format=tarfile.PAX_FORMAT) as tar:
                tar.extractall(unpack_tmp_folder)

            with open(os.path.join(unpack_tmp_folder,
                                   'metadata.json'), 'r') as f:
                metadata = json.load(f)
            metadata['export_version'] = 0.0
            with open(os.path.join(unpack_tmp_folder,
                                   'metadata.json'), 'w') as f:
                json.dump(metadata, f)

            with tarfile.open(filename, "w:gz", format=tarfile.PAX_FORMAT) as tar:
                tar.add(unpack_tmp_folder, arcname="")

            self.tearDownClass()
            self.setUpClass()

            with self.assertRaises(ValueError):
                import_data(filename, silent=True)
        finally:
            # Deleting the created temporary folders
            shutil.rmtree(export_file_tmp_folder, ignore_errors=True)
            shutil.rmtree(unpack_tmp_folder, ignore_errors=True)

    def test_3(self):
        """
        Test importing of nodes, that have links to unknown nodes.
        """
        import json
        import tarfile
        import os
        import shutil
        import tempfile

        from aiida.orm.importexport import export
        from aiida.common.folders import SandboxFolder
        from aiida.orm.data.structure import StructureData
        from aiida.orm import load_node

        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()
        try:
            node_label = "Test structure data"
            sd = StructureData()
            sd.label = str(node_label)
            sd.store()

            filename = os.path.join(temp_folder, "export.tar.gz")
            export([sd.dbnode], outfile=filename, silent=True)

            unpack = SandboxFolder()
            with tarfile.open(
                    filename, "r:gz", format=tarfile.PAX_FORMAT) as tar:
                tar.extractall(unpack.abspath)

            with open(unpack.get_abs_path('data.json'), 'r') as f:
                metadata = json.load(f)
            metadata['links_uuid'].append({
                'output': sd.uuid,
                'input': 'non-existing-uuid',
                'label': 'parent'
            })
            with open(unpack.get_abs_path('data.json'), 'w') as f:
                json.dump(metadata, f)

            with tarfile.open(
                    filename, "w:gz", format=tarfile.PAX_FORMAT) as tar:
                tar.add(unpack.abspath, arcname="")

            self.clean_db()

            with self.assertRaises(ValueError):
                import_data(filename, silent=True)

            import_data(filename, ignore_unknown_nodes=True, silent=True)
            self.assertEquals(load_node(sd.uuid).label, node_label)

        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)

    def test_4(self):
        """
        Test control of licenses.
        """
        from aiida.common.exceptions import LicensingException
        from aiida.common.folders import SandboxFolder
        from aiida.orm.importexport import export_tree

        from aiida.orm import DataFactory

        StructureData = DataFactory('structure')
        sd = StructureData()
        sd.source = {'license': 'GPL'}
        sd.store()

        folder = SandboxFolder()
        export_tree([sd.dbnode], folder=folder, silent=True,
                    allowed_licenses=['GPL'])
        # Folder should contain two files of metadata + nodes/
        self.assertEquals(len(folder.get_content_list()), 3)

        folder = SandboxFolder()
        export_tree([sd.dbnode], folder=folder, silent=True,
                    forbidden_licenses=['Academic'])
        # Folder should contain two files of metadata + nodes/
        self.assertEquals(len(folder.get_content_list()), 3)

        folder = SandboxFolder()
        with self.assertRaises(LicensingException):
            export_tree([sd.dbnode], folder=folder, silent=True,
                        allowed_licenses=['CC0'])

        folder = SandboxFolder()
        with self.assertRaises(LicensingException):
            export_tree([sd.dbnode], folder=folder, silent=True,
                        forbidden_licenses=['GPL'])

        def cc_filter(license):
            return license.startswith('CC')

        def gpl_filter(license):
            return license == 'GPL'

        def crashing_filter(license):
            raise NotImplementedError("not implemented yet")

        folder = SandboxFolder()
        with self.assertRaises(LicensingException):
            export_tree([sd.dbnode], folder=folder, silent=True,
                        allowed_licenses=cc_filter)

        folder = SandboxFolder()
        with self.assertRaises(LicensingException):
            export_tree([sd.dbnode], folder=folder, silent=True,
                        forbidden_licenses=gpl_filter)

        folder = SandboxFolder()
        with self.assertRaises(LicensingException):
            export_tree([sd.dbnode], folder=folder, silent=True,
                        allowed_licenses=crashing_filter)

        folder = SandboxFolder()
        with self.assertRaises(LicensingException):
            export_tree([sd.dbnode], folder=folder, silent=True,
                        forbidden_licenses=crashing_filter)

    def test_5(self):
        """
        This test checks that nodes belonging to different users are correctly
        exported & imported.
        """
        import os
        import shutil
        import tempfile

        from aiida.orm import load_node
        from aiida.orm.calculation.job import JobCalculation
        from aiida.orm.data.structure import StructureData
        from aiida.orm.importexport import export
        from aiida.common.datastructures import calc_states
        from aiida.common.links import LinkType
        from aiida.common.utils import get_configured_user_email

        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()
        try:
            # Create another user
            new_email = "newuser@new.n"
            user = self.backend.users.create(email=new_email)
            user.store()

            # Create a structure data node that has a calculation as output
            sd1 = StructureData()
            sd1.set_user(user)
            sd1.label = 'sd1'
            sd1.store()

            jc1 = JobCalculation()
            jc1.set_computer(self.computer)
            jc1.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            jc1.set_user(user)
            jc1.label = 'jc1'
            jc1.store()
            jc1.add_link_from(sd1)
            jc1._set_state(calc_states.PARSING)

            # Create some nodes from a different user
            sd2 = StructureData()
            sd2.set_user(user)
            sd2.label = 'sd2'
            sd2.store()
            sd2.add_link_from(jc1, label='l1', link_type=LinkType.CREATE)  # I assume jc1 CREATED sd2

            jc2 = JobCalculation()
            jc2.set_computer(self.computer)
            jc2.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            jc2.label = 'jc2'
            jc2.store()
            jc2.add_link_from(sd2, label='l2')
            jc2._set_state(calc_states.PARSING)

            sd3 = StructureData()
            sd3.label = 'sd3'
            sd3.store()
            sd3.add_link_from(jc2, label='l3', link_type=LinkType.CREATE)

            uuids_u1 = [sd1.uuid, jc1.uuid, sd2.uuid]
            uuids_u2 = [jc2.uuid, sd3.uuid]

            filename = os.path.join(temp_folder, "export.tar.gz")

            export([sd3.dbnode], outfile=filename, silent=True)
            self.clean_db()
            import_data(filename, silent=True)

            # Check that the imported nodes are correctly imported and that
            # the user assigned to the nodes is the right one
            for uuid in uuids_u1:
                self.assertEquals(load_node(uuid).get_user().email, new_email)
            for uuid in uuids_u2:
                self.assertEquals(load_node(uuid).get_user().email,
                                  get_configured_user_email())
        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)

    def test_6(self):
        """
        This test checks that nodes belonging to user A (which is not the
        default user) can be correctly exported, imported, enriched with nodes
        from the default user, re-exported & re-imported and that in the end
        all the nodes that have been finally imported belonging to the right
        users.
        """
        import os
        import shutil
        import tempfile

        from aiida.orm import load_node
        from aiida.orm.calculation.job import JobCalculation
        from aiida.orm.data.structure import StructureData
        from aiida.orm.importexport import export
        from aiida.common.datastructures import calc_states
        from aiida.common.links import LinkType
        from aiida.common.utils import get_configured_user_email

        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()
        try:
            # Create another user
            new_email = "newuser@new.n"
            user = self.backend.users.create(email=new_email)
            user.store()

            # Create a structure data node that has a calculation as output
            sd1 = StructureData()
            sd1.set_user(user)
            sd1.label = 'sd1'
            sd1.store()

            jc1 = JobCalculation()
            jc1.set_computer(self.computer)
            jc1.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            jc1.set_user(user)
            jc1.label = 'jc1'
            jc1.store()
            jc1.add_link_from(sd1)
            jc1._set_state(calc_states.PARSING)

            # Create some nodes from a different user
            sd2 = StructureData()
            sd2.set_user(user)
            sd2.label = 'sd2'
            sd2.store()
            sd2.add_link_from(jc1, label='l1', link_type=LinkType.CREATE)

            # Set the jc1 to FINISHED
            jc1._set_state(calc_states.FINISHED)

            # At this point we export the generated data
            filename1 = os.path.join(temp_folder, "export1.tar.gz")
            export([sd2.dbnode], outfile=filename1, silent=True)
            uuids1 = [sd1.uuid, jc1.uuid, sd2.uuid]
            self.clean_db()
            self.insert_data()
            import_data(filename1, silent=True)

            # Check that the imported nodes are correctly imported and that
            # the user assigned to the nodes is the right one
            for uuid in uuids1:
                self.assertEquals(load_node(uuid).get_user().email, new_email)

            # Now we continue to generate more data based on the imported
            # data
            sd2_imp = load_node(sd2.uuid)

            jc2 = JobCalculation()
            jc2.set_computer(self.computer)
            jc2.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            jc2.label = 'jc2'
            jc2.store()
            jc2.add_link_from(sd2_imp, label='l2')
            jc2._set_state(calc_states.PARSING)

            sd3 = StructureData()
            sd3.label = 'sd3'
            sd3.store()
            sd3.add_link_from(jc2, label='l3', link_type=LinkType.CREATE)

            # Set the jc2 to FINISHED
            jc2._set_state(calc_states.FINISHED)

            # Store the UUIDs of the nodes that should be checked
            # if they can be imported correctly.
            uuids2 = [jc2.uuid, sd3.uuid]

            filename2 = os.path.join(temp_folder, "export2.tar.gz")
            export([sd3.dbnode], outfile=filename2, silent=True)
            self.clean_db()
            self.insert_data()
            import_data(filename2, silent=True)

            # Check that the imported nodes are correctly imported and that
            # the user assigned to the nodes is the right one
            for uuid in uuids1:
                self.assertEquals(load_node(uuid).get_user().email, new_email)
            for uuid in uuids2:
                self.assertEquals(load_node(uuid).get_user().email,
                                  get_configured_user_email())

        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)

    def test_7(self):
        """
        This test checks that nodes that belong to a specific group are
        correctly imported and exported.
        """
        import os
        import shutil
        import tempfile

        from aiida.orm import load_node
        from aiida.orm.calculation.job import JobCalculation
        from aiida.orm.data.structure import StructureData
        from aiida.orm.importexport import export
        from aiida.common.datastructures import calc_states
        from aiida.orm.querybuilder import QueryBuilder

        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()
        try:
            # Create another user
            new_email = "newuser@new.n"
            user = self.backend.users.create(email=new_email)
            user.store()

            # Create a structure data node that has a calculation as output
            sd1 = StructureData()
            sd1.set_user(user)
            sd1.label = 'sd1'
            sd1.store()

            jc1 = JobCalculation()
            jc1.set_computer(self.computer)
            jc1.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            jc1.set_user(user)
            jc1.label = 'jc1'
            jc1.store()
            jc1.add_link_from(sd1)
            jc1._set_state(calc_states.PARSING)

            # Create a group and add the data inside
            from aiida.orm.group import Group
            g1 = Group(name="node_group")
            g1.store()
            g1.add_nodes([sd1, jc1])
            g1_uuid = g1.uuid

            # At this point we export the generated data
            filename1 = os.path.join(temp_folder, "export1.tar.gz")
            export([sd1.dbnode, jc1.dbnode, g1.dbgroup], outfile=filename1,
                   silent=True)
            n_uuids = [sd1.uuid, jc1.uuid]
            self.clean_db()
            self.insert_data()
            import_data(filename1, silent=True)

            # Check that the imported nodes are correctly imported and that
            # the user assigned to the nodes is the right one
            for uuid in n_uuids:
                self.assertEquals(load_node(uuid).get_user().email, new_email)

            # Check that the exported group is imported correctly
            qb = QueryBuilder()
            qb.append(Group, filters={'uuid': {'==': g1_uuid}})
            self.assertEquals(qb.count(), 1, "The group was not found.")
        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)

    def test_workfunction_1(self):
        import shutil, os, tempfile

        from aiida.work.workfunctions import workfunction
        from aiida.orm.data.float import Float
        from aiida.orm import load_node
        from aiida.orm.importexport import export
        from aiida.common.exceptions import NotExistent
        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()

        @workfunction
        def add(a, b):
            """Add 2 numbers"""
            return {'res': Float(a + b)}

        def max_(**kwargs):
            """select the max value"""
            max_val = max([(v.value, v) for v in kwargs.values()])
            return {'res': max_val[1]}

        try:
            # I'm creating a bunch of nuimbers
            a, b, c, d, e = (Float(i) for i in range(5))
            # this adds the maximum number between bcde to a.
            res = add(a=a, b=max_(b=b, c=c, d=d, e=e)['res'])['res']
            # These are the uuids that would be exported as well (as parents) if I wanted the final result
            uuids_values = [(a.uuid, a.value), (e.uuid, e.value), (res.uuid, res.value)]
            # These are the uuids that shouldn't be exported since it's a selection.
            not_wanted_uuids = [v.uuid for v in (b, c, d)]
            # At this point we export the generated data
            filename1 = os.path.join(temp_folder, "export1.tar.gz")
            export([res.dbnode], outfile=filename1, silent=True)
            self.clean_db()
            self.insert_data()
            import_data(filename1, silent=True)
            # Check that the imported nodes are correctly imported and that the value is preserved
            for uuid, value in uuids_values:
                self.assertEquals(load_node(uuid).value, value)
            for uuid in not_wanted_uuids:
                with self.assertRaises(NotExistent):
                    load_node(uuid)
        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)

    def test_workcalculation_2(self):
        import shutil, os, tempfile

        from aiida.orm.calculation.work import WorkCalculation
        from aiida.orm.data.float import Float
        from aiida.orm.data.int import Int
        from aiida.orm import load_node
        from aiida.common.links import LinkType
        from aiida.orm.importexport import export

        from aiida.common.exceptions import NotExistent
        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()

        try:
            master = WorkCalculation().store()
            slave = WorkCalculation().store()

            input_1 = Int(3).store()
            input_2 = Int(5).store()
            output_1 = Int(2).store()

            master.add_link_from(input_1, 'input_1', link_type=LinkType.INPUT)
            slave.add_link_from(master, 'CALL', link_type=LinkType.CALL)
            slave.add_link_from(input_2, 'input_2', link_type=LinkType.INPUT)
            output_1.add_link_from(master, 'CREATE', link_type=LinkType.CREATE)

            uuids_values = [(v.uuid, v.value) for v in (output_1,)]
            filename1 = os.path.join(temp_folder, "export1.tar.gz")
            export([output_1.dbnode], outfile=filename1, silent=True)
            self.clean_db()
            self.insert_data()
            import_data(filename1, silent=True)

            for uuid, value in uuids_values:
                self.assertEquals(load_node(uuid).value, value)

        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)

    def test_reexport(self):
        """
        Export something, import and reexport and check if everything is valid.
        The export is rather easy::

            ___       ___          ___
           |   | INP |   | CREATE |   |
           | p | --> | c | -----> | a |
           |___|     |___|        |___|

        """
        import os, shutil, tempfile, numpy as np, string, random
        from datetime import datetime

        from aiida.orm import Calculation, load_node, Group
        from aiida.orm.data.array import ArrayData
        from aiida.orm.data.parameter import ParameterData
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm.importexport import export
        from aiida.common.hashing import make_hash
        from aiida.common.links import LinkType
        def get_hash_from_db_content(groupname):
            qb = QueryBuilder()
            qb.append(ParameterData, tag='p', project='*')
            qb.append(Calculation, tag='c', project='*', edge_tag='p2c', edge_project=('label', 'type'))
            qb.append(ArrayData, tag='a', project='*', edge_tag='c2a', edge_project=('label', 'type'))
            qb.append(Group, filters={'name': groupname}, project='*', tag='g', group_of='a')
            # I want the query to contain something!
            self.assertTrue(qb.count() > 0)
            # The hash is given from the preservable entries in an export-import cycle,
            # uuids, attributes, labels, descriptions, arrays, link-labels, link-types:
            hash_ = make_hash([(
                item['p']['*'].get_attrs(),
                item['p']['*'].uuid,
                item['p']['*'].label,
                item['p']['*'].description,
                item['c']['*'].uuid,
                item['c']['*'].get_attrs(),
                item['a']['*'].get_attrs(),
                [item['a']['*'].get_array(name) for name in item['a']['*'].get_arraynames()],
                item['a']['*'].uuid,
                item['g']['*'].uuid,
                item['g']['*'].name,
                item['p2c']['label'],
                item['p2c']['type'],
                item['c2a']['label'],
                item['c2a']['type'],
                item['g']['*'].name,
            ) for item in qb.dict()])
            return hash_

        # Creating a folder for the import/export files
        temp_folder = tempfile.mkdtemp()
        chars = string.ascii_uppercase + string.digits
        size = 10
        groupname = 'test-group'
        try:
            nparr = np.random.random((4, 3, 2))
            trial_dict = {}
            # give some integers:
            trial_dict.update({str(k): np.random.randint(100) for k in range(10)})
            # give some floats:
            trial_dict.update({str(k): np.random.random() for k in range(10, 20)})
            # give some booleans:
            trial_dict.update({str(k): bool(np.random.randint(1)) for k in range(20, 30)})
            # give some datetime:
            trial_dict.update({str(k): datetime(
                year=2017,
                month=np.random.randint(1, 12),
                day=np.random.randint(1, 28)) for k in range(30, 40)})
            # give some text:
            trial_dict.update({str(k): ''.join(random.choice(chars) for _ in range(size)) for k in range(20, 30)})

            p = ParameterData(dict=trial_dict)
            p.label = str(datetime.now())
            p.description = 'd_' + str(datetime.now())
            p.store()
            c = Calculation()
            # setting also trial dict as attributes, but randomizing the keys)
            (c._set_attr(str(int(k) + np.random.randint(10)), v) for k, v in trial_dict.items())
            c.store()
            a = ArrayData()
            a.set_array('array', nparr)
            a.store()
            # LINKS
            # the calculation has input the parameters-instance
            c.add_link_from(p, label='input_parameters', link_type=LinkType.INPUT)
            # I want the array to be an output of the calculation
            a.add_link_from(c, label='output_array', link_type=LinkType.CREATE)
            g = Group(name='test-group')
            g.store()
            g.add_nodes(a)

            hash_from_dbcontent = get_hash_from_db_content(groupname)

            # I export and reimport 3 times in a row:
            for i in range(3):
                # Always new filename:
                filename = os.path.join(temp_folder, "export-{}.zip".format(i))
                # Loading the group from the string
                g = Group.get_from_string(groupname)
                # exporting based on all members of the group
                # this also checks if group memberships are preserved!
                export([g.dbgroup] + [n.dbnode for n in g.nodes], outfile=filename, silent=True)
                # cleaning the DB!
                self.clean_db()
                # reimporting the data from the file
                import_data(filename, silent=True, ignore_unknown_nodes=True)
                # creating the hash from db content
                new_hash = get_hash_from_db_content(groupname)
                # I check for equality against the first hash created, which implies that hashes
                # are equal in all iterations of this process
                self.assertEqual(hash_from_dbcontent, new_hash)

        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)


class TestComplex(AiidaTestCase):
    def test_complex_graph_import_export(self):
        """
        This test checks that a small and bit complex graph can be correctly
        exported and imported.

        It will create the graph, store it to the database, export it to a file
        and import it. In the end it will check if the initial nodes are present
        at the imported graph.
        """
        import tempfile
        import shutil
        import os

        from aiida.orm.calculation.job import JobCalculation
        from aiida.orm.data.folder import FolderData
        from aiida.orm.data.parameter import ParameterData
        from aiida.orm.data.remote import RemoteData
        from aiida.common.links import LinkType
        from aiida.orm.importexport import export, import_data
        from aiida.orm.utils import load_node
        from aiida.common.exceptions import NotExistent

        temp_folder = tempfile.mkdtemp()
        try:
            calc1 = JobCalculation()
            calc1.set_computer(self.computer)
            calc1.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            calc1.label = "calc1"
            calc1.store()
            calc1._set_state(u'RETRIEVING')

            pd1 = ParameterData()
            pd1.label = "pd1"
            pd1.store()

            pd2 = ParameterData()
            pd2.label = "pd2"
            pd2.store()

            rd1 = RemoteData()
            rd1.label = "rd1"
            rd1.set_remote_path("/x/y.py")
            rd1.set_computer(self.computer)
            rd1.store()
            rd1.add_link_from(calc1, link_type=LinkType.CREATE)

            calc2 = JobCalculation()
            calc2.set_computer(self.computer)
            calc2.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})
            calc2.label = "calc2"
            calc2.store()
            calc2.add_link_from(pd1, link_type=LinkType.INPUT)
            calc2.add_link_from(pd2, link_type=LinkType.INPUT)
            calc2.add_link_from(rd1, link_type=LinkType.INPUT)
            calc2._set_state(u'SUBMITTING')

            fd1 = FolderData()
            fd1.label = "fd1"
            fd1.store()
            fd1.add_link_from(calc2, link_type=LinkType.CREATE)

            node_uuids_labels = {calc1.uuid: calc1.label, pd1.uuid: pd1.label,
                                 pd2.uuid: pd2.label, rd1.uuid: rd1.label,
                                 calc2.uuid: calc2.label, fd1.uuid: fd1.label}

            filename = os.path.join(temp_folder, "export.tar.gz")
            export([fd1.dbnode], outfile=filename, silent=True)

            self.clean_db()

            import_data(filename, silent=True, ignore_unknown_nodes=True)

            for uuid, label in node_uuids_labels.iteritems():
                try:
                    load_node(uuid)
                except NotExistent:
                    self.fail("Node with UUID {} and label {} was not "
                              "found.".format(uuid, label))

        finally:
            # Deleting the created temporary folder
            shutil.rmtree(temp_folder, ignore_errors=True)


class TestComputer(AiidaTestCase):

    def setUp(self):
        self.clean_db()
        self.insert_data()

    def tearDown(self):
        pass

    def test_same_computer_import(self):
        """
        Test that you can import nodes in steps without any problems. In this
        test we will import a first calculation and then a second one. The
        import should work as expected and have in the end two job
        calculations.

        Each calculation is related to the same computer. In the end we should
        have only one computer
        """
        import os
        import shutil
        import tempfile

        from aiida.orm.importexport import export
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm.computer import Computer
        from aiida.orm.calculation.job import JobCalculation

        # Creating a folder for the import/export files
        export_file_tmp_folder = tempfile.mkdtemp()
        unpack_tmp_folder = tempfile.mkdtemp()

        try:
            # Store two job calculation related to the same computer
            calc1_label = "calc1"
            calc1 = JobCalculation()
            calc1.set_computer(self.computer)
            calc1.set_resources({"num_machines": 1,
                                 "num_mpiprocs_per_machine": 1})
            calc1.label = calc1_label
            calc1.store()
            calc1._set_state(u'RETRIEVING')

            calc2_label = "calc2"
            calc2 = JobCalculation()
            calc2.set_computer(self.computer)
            calc2.set_resources({"num_machines": 2,
                                 "num_mpiprocs_per_machine": 2})
            calc2.label = calc2_label
            calc2.store()
            calc2._set_state(u'RETRIEVING')

            # Store locally the computer name
            comp_name = unicode(self.computer.name)
            comp_uuid = unicode(self.computer.uuid)

            # Export the first job calculation
            filename1 = os.path.join(export_file_tmp_folder, "export1.tar.gz")
            export([calc1.dbnode], outfile=filename1, silent=True)

            # Export the second job calculation
            filename2 = os.path.join(export_file_tmp_folder, "export2.tar.gz")
            export([calc2.dbnode], outfile=filename2, silent=True)

            # Clean the local database
            self.clean_db()

            # Check that there are no computers
            qb = QueryBuilder()
            qb.append(Computer, project=['*'])
            self.assertEqual(qb.count(), 0, "There should not be any computers"
                                            "in the database at this point.")

            # Check that there are no calculations
            qb = QueryBuilder()
            qb.append(JobCalculation, project=['*'])
            self.assertEqual(qb.count(), 0, "There should not be any "
                                            "calculations in the database at "
                                            "this point.")

            # Import the first calculation
            import_data(filename1, silent=True)

            # Check that the calculation computer is imported correctly.
            qb = QueryBuilder()
            qb.append(JobCalculation, project=['label'])
            self.assertEqual(qb.count(), 1, "Only one calculation should be "
                                            "found.")
            self.assertEqual(unicode(qb.first()[0]), calc1_label,
                             "The calculation label is not correct.")

            # Check that the referenced computer is imported correctly.
            qb = QueryBuilder()
            qb.append(Computer, project=['name', 'uuid', 'id'])
            self.assertEqual(qb.count(), 1, "Only one computer should be "
                                            "found.")
            self.assertEqual(unicode(qb.first()[0]), comp_name,
                             "The computer name is not correct.")
            self.assertEqual(unicode(qb.first()[1]), comp_uuid,
                             "The computer uuid is not correct.")

            # Store the id of the computer
            comp_id = qb.first()[2]

            # Import the second calculation
            import_data(filename2, silent=True)

            # Check that the number of computers remains the same and its data
            # did not change.
            qb = QueryBuilder()
            qb.append(Computer, project=['name', 'uuid', 'id'])
            self.assertEqual(qb.count(), 1, "Only one computer should be "
                                            "found.")
            self.assertEqual(unicode(qb.first()[0]), comp_name,
                             "The computer name is not correct.")
            self.assertEqual(unicode(qb.first()[1]), comp_uuid,
                             "The computer uuid is not correct.")
            self.assertEqual(qb.first()[2], comp_id,
                             "The computer id is not correct.")

            # Check that now you have two calculations attached to the same
            # computer.
            qb = QueryBuilder()
            qb.append(Computer, tag='comp')
            qb.append(JobCalculation, has_computer='comp', project=['label'])
            self.assertEqual(qb.count(), 2, "Two calculations should be "
                                            "found.")
            ret_labels = set(_ for [_] in qb.all())
            self.assertEqual(ret_labels, set([calc1_label, calc2_label]),
                             "The labels of the calculations are not correct.")

        finally:
            # Deleting the created temporary folders
            shutil.rmtree(export_file_tmp_folder, ignore_errors=True)
            shutil.rmtree(unpack_tmp_folder, ignore_errors=True)

    def test_same_computer_different_name_import(self):
        """
        This test checks that if the computer is re-imported with a different
        name to the same database, then the original computer will not be
        renamed. It also checks that the names were correctly imported (without
        any change since there is no computer name collision)
        """
        import os
        import shutil
        import tempfile

        from aiida.orm.importexport import export
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm.computer import Computer
        from aiida.orm.calculation.job import JobCalculation

        # Creating a folder for the import/export files
        export_file_tmp_folder = tempfile.mkdtemp()
        unpack_tmp_folder = tempfile.mkdtemp()

        try:
            # Store a calculation
            calc1_label = "calc1"
            calc1 = JobCalculation()
            calc1.set_computer(self.computer)
            calc1.set_resources({"num_machines": 1,
                                 "num_mpiprocs_per_machine": 1})
            calc1.label = calc1_label
            calc1.store()
            calc1._set_state(u'RETRIEVING')

            # Store locally the computer name
            comp1_name = unicode(self.computer.name)

            # Export the first job calculation
            filename1 = os.path.join(export_file_tmp_folder, "export1.tar.gz")
            export([calc1.dbnode], outfile=filename1, silent=True)

            # Rename the computer
            self.computer.set_name(comp1_name + "_updated")

            # Store a second calculation
            calc2_label = "calc2"
            calc2 = JobCalculation()
            calc2.set_computer(self.computer)
            calc2.set_resources({"num_machines": 2,
                                 "num_mpiprocs_per_machine": 2})
            calc2.label = calc2_label
            calc2.store()
            calc2._set_state(u'RETRIEVING')

            # Export the second job calculation
            filename2 = os.path.join(export_file_tmp_folder, "export2.tar.gz")
            export([calc2.dbnode], outfile=filename2, silent=True)

            # Clean the local database
            self.clean_db()

            # Check that there are no computers
            qb = QueryBuilder()
            qb.append(Computer, project=['*'])
            self.assertEqual(qb.count(), 0, "There should not be any computers"
                                            "in the database at this point.")

            # Check that there are no calculations
            qb = QueryBuilder()
            qb.append(JobCalculation, project=['*'])
            self.assertEqual(qb.count(), 0, "There should not be any "
                                            "calculations in the database at "
                                            "this point.")

            # Import the first calculation
            import_data(filename1, silent=True)

            # Check that the calculation computer is imported correctly.
            qb = QueryBuilder()
            qb.append(JobCalculation, project=['label'])
            self.assertEqual(qb.count(), 1, "Only one calculation should be "
                                            "found.")
            self.assertEqual(unicode(qb.first()[0]), calc1_label,
                             "The calculation label is not correct.")

            # Check that the referenced computer is imported correctly.
            qb = QueryBuilder()
            qb.append(Computer, project=['name', 'uuid', 'id'])
            self.assertEqual(qb.count(), 1, "Only one computer should be "
                                            "found.")
            self.assertEqual(unicode(qb.first()[0]), comp1_name,
                             "The computer name is not correct.")

            # Import the second calculation
            import_data(filename2, silent=True)

            # Check that the number of computers remains the same and its data
            # did not change.
            qb = QueryBuilder()
            qb.append(Computer, project=['name'])
            self.assertEqual(qb.count(), 1, "Only one computer should be "
                                            "found.")
            self.assertEqual(unicode(qb.first()[0]), comp1_name,
                             "The computer name is not correct.")

        finally:
            # Deleting the created temporary folders
            shutil.rmtree(export_file_tmp_folder, ignore_errors=True)
            shutil.rmtree(unpack_tmp_folder, ignore_errors=True)

    def test_different_computer_same_name_import(self):
        """
        This test checks that if there is a name collision, the imported
        computers are renamed accordingly.
        """
        import os
        import shutil
        import tempfile

        from aiida.orm.importexport import export
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm.computer import Computer
        from aiida.orm.calculation.job import JobCalculation
        from aiida.orm.importexport import COMP_DUPL_SUFFIX

        # Creating a folder for the import/export files
        export_file_tmp_folder = tempfile.mkdtemp()
        unpack_tmp_folder = tempfile.mkdtemp()

        try:
            # Set the computer name
            comp1_name = "localhost_1"
            self.computer.set_name(comp1_name)

            # Store a calculation
            calc1_label = "calc1"
            calc1 = JobCalculation()
            calc1.set_computer(self.computer)
            calc1.set_resources({"num_machines": 1,
                                 "num_mpiprocs_per_machine": 1})
            calc1.label = calc1_label
            calc1.store()
            calc1._set_state(u'RETRIEVING')

            # Export the first job calculation
            filename1 = os.path.join(export_file_tmp_folder, "export1.tar.gz")
            export([calc1.dbnode], outfile=filename1, silent=True)

            # Reset the database
            self.clean_db()
            self.insert_data()

            # Set the computer name to the same name as before
            self.computer.set_name(comp1_name)

            # Store a second calculation
            calc2_label = "calc2"
            calc2 = JobCalculation()
            calc2.set_computer(self.computer)
            calc2.set_resources({"num_machines": 2,
                                 "num_mpiprocs_per_machine": 2})
            calc2.label = calc2_label
            calc2.store()
            calc2._set_state(u'RETRIEVING')

            # Export the second job calculation
            filename2 = os.path.join(export_file_tmp_folder, "export2.tar.gz")
            export([calc2.dbnode], outfile=filename2, silent=True)

            # Reset the database
            self.clean_db()
            self.insert_data()

            # Set the computer name to the same name as before
            self.computer.set_name(comp1_name)

            # Store a third calculation
            calc3_label = "calc3"
            calc3 = JobCalculation()
            calc3.set_computer(self.computer)
            calc3.set_resources({"num_machines": 2,
                                 "num_mpiprocs_per_machine": 2})
            calc3.label = calc3_label
            calc3.store()
            calc3._set_state(u'RETRIEVING')

            # Export the third job calculation
            filename3 = os.path.join(export_file_tmp_folder, "export3.tar.gz")
            export([calc3.dbnode], outfile=filename3, silent=True)

            # Clean the local database
            self.clean_db()

            # Check that there are no computers
            qb = QueryBuilder()
            qb.append(Computer, project=['*'])
            self.assertEqual(qb.count(), 0, "There should not be any computers"
                                            "in the database at this point.")

            # Check that there are no calculations
            qb = QueryBuilder()
            qb.append(JobCalculation, project=['*'])
            self.assertEqual(qb.count(), 0, "There should not be any "
                                            "calculations in the database at "
                                            "this point.")

            # Import all the calculations
            import_data(filename1, silent=True)
            import_data(filename2, silent=True)
            import_data(filename3, silent=True)

            # Retrieve the calculation-computer pairs
            qb = QueryBuilder()
            qb.append(JobCalculation, project=['label'], tag='jcalc')
            qb.append(Computer, project=['name'],
                      computer_of='jcalc')
            self.assertEqual(qb.count(), 3, "Three combinations expected.")
            res = qb.all()
            self.assertIn([calc1_label, comp1_name], res,
                          "Calc-Computer combination not found.")
            self.assertIn([calc2_label,
                           comp1_name + COMP_DUPL_SUFFIX.format(0)], res,
                          "Calc-Computer combination not found.")
            self.assertIn([calc3_label,
                           comp1_name + COMP_DUPL_SUFFIX.format(1)], res,
                          "Calc-Computer combination not found.")
        finally:
            # Deleting the created temporary folders
            shutil.rmtree(export_file_tmp_folder, ignore_errors=True)
            shutil.rmtree(unpack_tmp_folder, ignore_errors=True)

    def test_correct_import_of_computer_json_params(self):
        """
        This test checks that the metadata and transport params are
        exported and imported correctly in both backends.
        """
        import os
        import shutil
        import tempfile

        from aiida.orm.importexport import export
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm.computer import Computer
        from aiida.orm.calculation.job import JobCalculation

        # Creating a folder for the import/export files
        export_file_tmp_folder = tempfile.mkdtemp()
        unpack_tmp_folder = tempfile.mkdtemp()

        try:
            # Set the computer name
            comp1_name = "localhost_1"
            comp1_metadata = {
                u'workdir': u'/tmp/aiida'
            }
            comp1_transport_params = {
                u'key1': u'value1',
                u'key2': 2
            }
            self.computer.set_name(comp1_name)
            self.computer._set_metadata(comp1_metadata)
            self.computer.set_transport_params(comp1_transport_params)

            # Store a calculation
            calc1_label = "calc1"
            calc1 = JobCalculation()
            calc1.set_computer(self.computer)
            calc1.set_resources({"num_machines": 1,
                                 "num_mpiprocs_per_machine": 1})
            calc1.label = calc1_label
            calc1.store()
            calc1._set_state(u'RETRIEVING')

            # Export the first job calculation
            filename1 = os.path.join(export_file_tmp_folder, "export1.tar.gz")
            export([calc1.dbnode], outfile=filename1, silent=True)

            # Clean the local database
            self.clean_db()
            # Import the data
            import_data(filename1, silent=True)

            qb = QueryBuilder()
            qb.append(Computer, project=['transport_params', '_metadata'],
                      tag="comp")
            self.assertEqual(qb.count(), 1, "Expected only one computer")

            res = qb.dict()[0]
            self.assertEqual(res['comp']['transport_params'],
                             comp1_transport_params,
                             "Not the expected transport parameters "
                             "were found")
            self.assertEqual(res['comp']['_metadata'],
                             comp1_metadata,
                             "Not the expected metadata were found")
        finally:
            # Deleting the created temporary folders
            shutil.rmtree(export_file_tmp_folder, ignore_errors=True)
            shutil.rmtree(unpack_tmp_folder, ignore_errors=True)

    def test_import_of_django_sqla_export_file(self):
        """
        Check why sqla import manages to import the django export file correctly
        """
        import inspect
        import os
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm.computer import Computer

        for filename in ('export_dj_comp_test.aiida',
                         'export_sqla_comp_test.aiida'):
            curr_path = inspect.getfile(inspect.currentframe())
            folder_path = os.path.dirname(curr_path)
            relative_folder_path = ("export_import_test_files/" + filename)
            test_file_path = os.path.join(folder_path, relative_folder_path)

            # Clean the database
            self.clean_db()

            # Import the needed data
            import_data(test_file_path, silent=True)

            # The expected metadata & transport parameters
            comp1_metadata = {
                u'workdir': u'/tmp/aiida'
            }
            comp1_transport_params = {
                u'key1': u'value1',
                u'key2': 2
            }

            # Check that we got the correct metadata & transport parameters
            qb = QueryBuilder()
            qb.append(Computer, project=['transport_params', '_metadata'],
                      tag="comp")
            self.assertEqual(qb.count(), 1, "Expected only one computer")

            res = qb.dict()[0]

            self.assertEqual(res['comp']['transport_params'],
                             comp1_transport_params,
                             "Not the expected transport parameters "
                             "were found")
            self.assertEqual(res['comp']['_metadata'],
                             comp1_metadata,
                             "Not the expected metadata were found")


class TestLinks(AiidaTestCase):

    def setUp(self):
        self.clean_db()
        self.insert_data()

    def tearDown(self):
        pass

    def get_all_node_links(self):
        """
        """
        from aiida.orm import load_node, Node
        from aiida.orm.querybuilder import QueryBuilder
        qb = QueryBuilder()
        qb.append(Node, project='uuid', tag='input')
        qb.append(Node, project='uuid', tag='output', edge_project=['label', 'type'], output_of='input')
        return qb.all()

    def test_input_and_create_links(self):
        """
        Simple test that will verify that INPUT and CREATE links are properly exported and
        correctly recreated upon import.
        """
        import os, shutil, tempfile

        from aiida.orm.data.int import Int
        from aiida.orm.importexport import export
        from aiida.orm.calculation.work import WorkCalculation
        from aiida.common.links import LinkType
        from aiida.common.exceptions import NotExistent

        tmp_folder = tempfile.mkdtemp()

        try:
            node_work = WorkCalculation().store()
            node_input = Int(1).store()
            node_output = Int(2).store()

            node_work.add_link_from(node_input, 'input', link_type=LinkType.INPUT)
            node_output.add_link_from(node_work, 'output', link_type=LinkType.CREATE)

            export_links = self.get_all_node_links()
            export_file = os.path.join(tmp_folder, 'export.tar.gz')
            export([node_output.dbnode], outfile=export_file, silent=True)

            self.clean_db()
            self.insert_data()

            import_data(export_file, silent=True)
            import_links = self.get_all_node_links()

            export_set = [tuple(_) for _ in export_links]
            import_set = [tuple(_) for _ in import_links]

            self.assertEquals(set(export_set), set(import_set))
        finally:
            shutil.rmtree(tmp_folder, ignore_errors=True)

    def test_input_and_create_links_proper(self):
        """
        Check that CALL links are not followed in the export procedure with
        dangling links as a consequence::

               ---------->---------
            __|_       ___        _|_
           |    | INP |   | CALL |   |
           | i1 | --> | C | <--  | W |
           |____|     |___|      |___|
                        |
                        v  CREATE
                       ____ 
                      |    |
                      | o1 |
                      |____|

        """
        import os, shutil, tempfile

        from aiida.orm.data.int import Int
        from aiida.orm import Node, Data
        from aiida.orm.importexport import export
        from aiida.orm.calculation import Calculation
        from aiida.orm.calculation.inline import InlineCalculation
        from aiida.orm.calculation.work import WorkCalculation
        from aiida.common.links import LinkType
        from aiida.common.exceptions import NotExistent
        from aiida.orm.querybuilder import QueryBuilder
        tmp_folder = tempfile.mkdtemp()

        try:
            node_calc = InlineCalculation().store()
            node_work = WorkCalculation().store()
            node_input = Int(1).store()
            node_output = Int(2).store()

            node_work.add_link_from(node_input, 'input-to-work', link_type=LinkType.INPUT)
            node_calc.add_link_from(node_input, 'input-to-calc', link_type=LinkType.INPUT)
            node_calc.add_link_from(node_work, 'call', link_type=LinkType.CALL)
            node_output.add_link_from(node_calc, 'output', link_type=LinkType.CREATE)

            export_links = QueryBuilder().append(
                Data, project='uuid').append(
                InlineCalculation, project='uuid', edge_project=['label', 'type'],
                edge_filters={'type': {'in': (LinkType.INPUT.value,)}}
            ).all() + QueryBuilder().append(
                InlineCalculation, project='uuid').append(
                Data, project='uuid', edge_project=['label', 'type'],
                edge_filters={'type': {'in': (LinkType.CREATE.value,)}}
            ).all()

            export_file = os.path.join(tmp_folder, 'export.tar.gz')
            export([node_output.dbnode], outfile=export_file, silent=True)

            self.clean_db()
            self.insert_data()

            import_data(export_file, silent=True)
            import_links = self.get_all_node_links()

            export_set = [tuple(_) for _ in export_links]
            import_set = [tuple(_) for _ in import_links]

            self.assertEquals(set(export_set), set(import_set))
        finally:
            shutil.rmtree(tmp_folder, ignore_errors=True)

    def test_links_for_workflows(self):
        """
        Check that CALL links are not followed in the export procedure, and the only creation
        is followed for data::

            ____       ____        ____
           |    | INP |    | CALL |    |
           | i1 | --> | w1 | <--- | w2 |
           |____|     |____|      |____|
                       | |
                CREATE v v RETURN
                       ____
                      |    |
                      | o1 |
                      |____|

        """
        import os, shutil, tempfile

        from aiida.orm.data.int import Int
        from aiida.orm import Node, Data
        from aiida.orm.importexport import export
        from aiida.orm.calculation import Calculation
        from aiida.orm.calculation.inline import InlineCalculation
        from aiida.orm.calculation.work import WorkCalculation
        from aiida.common.links import LinkType
        from aiida.common.exceptions import NotExistent
        from aiida.orm.querybuilder import QueryBuilder
        tmp_folder = tempfile.mkdtemp()

        try:
            w1 = WorkCalculation().store()
            w2 = WorkCalculation().store()
            i1 = Int(1).store()
            o1 = Int(2).store()

            w1.add_link_from(i1, 'input-i1', link_type=LinkType.INPUT)
            w1.add_link_from(w2, 'call', link_type=LinkType.CALL)
            o1.add_link_from(w1, 'output', link_type=LinkType.CREATE)
            o1.add_link_from(w1, 'return', link_type=LinkType.RETURN)

            uuids_wanted = set(_.uuid for _ in (w1, o1, i1))
            links_wanted = [l for l in self.get_all_node_links() if l[3] in ('createlink', 'inputlink')]

            export_file_1 = os.path.join(tmp_folder, 'export-1.tar.gz')
            export_file_2 = os.path.join(tmp_folder, 'export-2.tar.gz')
            export([o1.dbnode], outfile=export_file_1, silent=True)
            export([w1.dbnode], outfile=export_file_2, silent=True)

            self.clean_db()
            self.insert_data()

            import_data(export_file_1, silent=True)
            links_in_db = self.get_all_node_links()
            self.assertEquals(sorted(links_wanted), sorted(links_in_db))

            self.clean_db()
            self.insert_data()

            import_data(export_file_2, silent=True)
            links_in_db = self.get_all_node_links()
            self.assertEquals(sorted(links_wanted), sorted(links_in_db))



        finally:
            shutil.rmtree(tmp_folder, ignore_errors=True)
