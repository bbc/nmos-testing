# Copyright (C) 2019 Advanced Media Workflow Association
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from GenericTest import GenericTest, NMOSTestException
from TestHelper import compare_json
from NMOSUtils import NMOSUtils, SCHEDULED_ABSOLUTE_ACTIVATION, SCHEDULED_RELATIVE_ACTIVATION
from is08.action import Action
from is08.activation import Activation
from is08.inputs import getInputList
from is08.outputs import getOutputList
from is08.active import Active
from is08.io import IO
from is08.testConfig import globalConfig
import time
import copy

MAPPING_API_KEY = "channelmapping"


class IS0801Test(GenericTest):
    """
    Runs IS-08-01-Test
    """

    def __init__(self, apis):
        # Don't auto-test /map/active/{outputId} as the tests cannot find the {outputId}s automatically
        omit_paths = [
            "/map/active/{outputId}"
        ]
        GenericTest.__init__(self, apis, omit_paths)
        globalConfig.apiUrl = apis[MAPPING_API_KEY]['url']
        globalConfig.testSuite = self
        globalConfig.apiKey = MAPPING_API_KEY

    def test_01_io_content_match(self, test):
        """Content of the /io view matches resources elsewhere in the API"""
        globalConfig.test = test

        inputList = getInputList()
        outputList = getOutputList()
        ioInstance = IO()
        ioJSON = ioInstance.getIOAsJSON()

        mockIoResource = {"inputs": {}, "outputs": {}}

        for input in inputList:
            mockIoResource["inputs"][input.id] = input.assembleInputObject()

        for output in outputList:
            mockIoResource["outputs"][output.id] = output.assembleOutputObject()

        if compare_json(mockIoResource, ioJSON):
            return test.PASS()
        else:
            return test.FAIL("IO Resource does not correctly reflect the API resources")

    def test_02_immediate_activation(self, test):
        """Immediate activation can be called on the API"""
        globalConfig.test = test

        outputList = getOutputList()
        testRouteAction = outputList[0].findAcceptableTestRoute()
        activation = Activation()
        activation.addAction(testRouteAction)
        activation.fireActivation()

        activeResource = Active()
        activeResource.assertActionCompleted(testRouteAction)
        return test.PASS()

    def test_03_relative_activation(self, test):
        """Relative offset activations can be called on the API"""
        globalConfig.test = test

        offset = "2:0"
        self.check_delayed_activation(offset, SCHEDULED_RELATIVE_ACTIVATION)

        return test.PASS()

    def test_04_absolute_activation(self, test):
        """Absolute offset activations can be called on the API"""
        globalConfig.test = test

        timestamp = NMOSUtils(globalConfig.apiUrl).get_TAI_time(offset=2.0)
        self.check_delayed_activation(timestamp, SCHEDULED_ABSOLUTE_ACTIVATION)

        return test.PASS()

    def test_05_delete_activations(self, test):
        """Activations can be deleted once created"""
        globalConfig.test = test

        Active().unrouteAll()
        outputList = getOutputList()
        testRouteAction = outputList[0].findAcceptableTestRoute()
        activation = Activation()
        activation.addAction(testRouteAction)
        activation.type = SCHEDULED_RELATIVE_ACTIVATION
        activation.activationTimestamp = "2:0"
        try:
            activation.fireActivation()
        except NMOSTestException as e:
            time.sleep(2)
            raise e

        time.sleep(1)

        activation.delete()

        return test.PASS()

    def test_06_locking_response(self, test):
        """Attempting to change a locked route results in a 423 response"""
        globalConfig.test = test

        outputList = getOutputList()
        testRouteAction = outputList[0].findAcceptableTestRoute()
        activation = Activation()
        activation.addAction(testRouteAction)
        activation.type = SCHEDULED_RELATIVE_ACTIVATION
        activation.activationTimestamp = "5:0"
        activation.fireActivation()
        activation.checkLock()

        return test.PASS()

    def test_07_unrouted_channels_null(self, test):
        """Channels in the active resource where no input channel is routed have `null`
        set as the `input` and `channel_index`"""
        globalConfig.test = test

        activeInstance = Active()

        outputList = getOutputList()
        for outputInstance in outputList:
            channelList = outputInstance.getChannelList()
            for channelID in range(0, len(channelList)):
                inputChannelIndex = activeInstance.getInputChannelIndex(
                    outputInstance,
                    channelID
                )
                inputChannelName = activeInstance.getInputChannelName(
                    outputInstance,
                    channelID
                )
                if inputChannelIndex is None or inputChannelName is None:
                    if inputChannelIndex != inputChannelName:
                        msg = ("Both the channel index and name must be set"
                               " to `null` when the a channel is not routed")
                        test.FAIL(msg)

        return test.PASS()

    def test_08_no_reentrant_loops(self, test):
        """If the device allows re-entrant  matrices, the constraints are set such that it
        is not possible to create a loop"""
        globalConfig.test = test

        forbiddenRoutes = []
        outputList = getOutputList()
        inputList = getInputList()
        for outputInstance in outputList:
            sourceID = outputInstance.getSourceID()
            for inputInstance in inputList:
                inputParent = inputInstance.getParent()
                if sourceID == inputParent:
                    route = {
                        "input": inputInstance,
                        "output": outputInstance
                    }
                    forbiddenRoutes.append(route)

        for route in forbiddenRoutes:
            outputCaps = route['output'].getCaps()
            msg = ("It is possible to create a loop using re-entrant matricies"
                   " between input {} and output {}".format(route['input'].id, route['output'].id))
            try:
                routableInputs = outputCaps['routable_inputs']
            except KeyError:
                return test.FAIL(msg)
            if route['output'].id not in routableInputs:
                return test.FAIL(msg)
        return test.PASS()

    def test_09_props_name(self, test):
        """Human readable name provided in the props resource"""
        return test.MANUAL()

    def test_10_props_description(self, test):
        """Human readable description provided in the props resource"""
        return test.MANUAL()

    def test_11_inputs_have_channels(self, test):
        """Inputs have at least one channel represented in their channels resource"""
        globalConfig.test = test
        inputList = getInputList()
        for inputInstance in inputList:
            channels = inputInstance.getChannelList()
            if len(channels) == 0:
                return test.FAIL("Inputs must have at least one channel")
        return test.PASS()

    def test_12_outputs_have_channels(self, test):
        """Outputs have at least one channel represented in their channels resource"""
        globalConfig.test = test

        outputList = getOutputList()
        for outputInstance in outputList:
            channels = outputInstance.getChannelList()
            if len(channels) == 0:
                return test.FAIL("Outputs must have at least one channel")
        return test.PASS()

    def test_13_violate_routing_constraints_rejected(self, test):
        """Attempting to violate routing constraints results in an HTTP 400 response"""
        globalConfig.test = test

        outputList = getOutputList()
        constrainedOutputList = []
        for outputInstance in outputList:
            constraints = outputInstance.getCaps()
            try:
                routableInputs = constraints['routable_inputs']
            except KeyError:
                pass
            else:
                constrainedOutputList.append(
                    {
                        "output": outputInstance,
                        "routableInputs": routableInputs
                    }
                )

        if len(constrainedOutputList) == 0:
            return test.NA("Could not test - no outputs have routing constraints set.")

        inputList = getInputList()
        inputIDList = []
        for inputInstance in inputList:
            inputIDList.append(inputInstance.id)

        for constrainedOutput in constrainedOutputList:
            forbiddenRoutes = copy.deepcopy(inputIDList)

            for routableInputID in constrainedOutput['routableInputs']:
                forbiddenRoutes.remove(routableInputID)

            if len(forbiddenRoutes) > 0:

                action = Action(forbiddenRoutes[0], constrainedOutput['output'].id)
                activation = Activation()
                activation.addAction(action)

                try:
                    activation.checkReject()
                except NMOSTestException:
                    msg = ("Was able to create a forbidden route between input {}"
                           " and output {} despite routing constraint."
                           "".format(forbiddenRoutes[0], outputInstance.id))
                    return test.FAIL(msg)
        return test.NA("Could not test - no route is forbidden.")

    def test_14_reordering_constraint(self, test):
        """It is not possible to re-order channels when re-ordering is
        set to `false`"""
        globalConfig.test = test

        inputList = getInputList()

        constrainedInputs = []
        constraintSet = False
        for inputInstance in inputList:
            if not inputInstance.getReordering():
                constrainedInputs.append(inputInstance)
                constraintSet = True

        if not constraintSet:
            return test.NA("No inputs prevent re-ordering.")

        # Filter out inputs where the constraint can't be tested because the
        # block size prevents re-ordering anyway
        filteredInputs = []
        for inputInstance in constrainedInputs:
            blockSize = inputInstance.getBlockSize()
            if len(inputInstance.getChannelList) >= blockSize * 2:
                # Constraint makes no sense, can't re-order to to block size
                filteredInputs.append(inputInstance)

        # Filter out inputs where there is no output that channels could be
        # re-ordered into
        targetOutputList = {}
        testableInputs = []
        for inputInstance in filteredInputs:
            routableOutputList = inputInstance.getRoutableOutputs()
            for outputInstance in routableOutputList:
                if len(outputInstance.getChannelList) >= inputInstance.getBlockSize() * 2:
                    targetOutputList[inputInstance.id] = outputInstance
            if inputInstance.id in targetOutputList.keys:
                testableInputs.append(inputInstance)

        # Cross over blocks one and two on an input and output
        # e.g for a block size of 2:
        # IN            OUT
        # 0 ____   ____ 0
        # 1 ___ \ / ___ 1
        #      \ X /
        #       X X
        # 2 ___/ X \___ 2
        # 3 ____/ \____ 3
        activation = Activation()
        for inputInstance in testableInputs:
            for inputChannelIndex in range(0, inputInstance.getBlockSize()):
                outputChannelIndex = inputChannelIndex + blockSize
                blockOneAction = Action(
                    inputInstance.id,
                    targetOutputList[inputInstance.id],
                    inputChannelIndex,
                    outputChannelIndex
                )
                blockTwoAction = Action(
                    inputInstance.id,
                    targetOutputList[inputInstance.id],
                    outputChannelIndex,
                    inputChannelIndex
                )
                activation.addAction(blockOneAction)
                activation.addAction(blockTwoAction)

        try:
            activation.fireActivation()
        except NMOSTestException:
            return test.PASS()

        return test.FAIL("Channels could be re-ordered despite re-ordering constraint.")

    def test_15_block_constraint(self, test):
        """It is not possible to make an out-of-block route when block_size
        is anything other than 1"""
        globalConfig.test = test

        inputList = getInputList()
        constraintSet = False
        constrainedInputs = []
        for inputInstance in inputList:
            if inputInstance.getBlockSize() > 1:
                constraintSet = True
                constrainedInputs.append(inputInstance)

        if not constraintSet:
            return test.NA("No inputs constrain by block.")

        chosenInput = constrainedInputs[0]
        output = chosenInput.getRoutableOutputs()
        action = Action(
            chosenInput.id,
            output.id
        )
        activation = Activation()
        activation.addAction(action)
        try:
            activation.fireActivation()
        except NMOSTestException:
            return test.PASS()

        return test.FAIL("Was able to break block size routing constraint")

    def check_delayed_activation(self, activationTime, activationType):
        active = Active()
        active.unrouteAll()
        preActivationState = active.buildJSONObject()

        outputList = getOutputList()
        testRouteAction = outputList[0].findAcceptableTestRoute()
        activation = Activation()
        activation.addAction(testRouteAction)
        activation.type = activationType
        activation.activationTimestamp = activationTime
        try:
            activation.fireActivation()
        except NMOSTestException as e:
            time.sleep(2)
            raise e

        pendingState = active.buildJSONObject()
        if not compare_json(preActivationState, pendingState):
            msg = globalConfig.test.FAIL("Scheduled Activation completed immediately")
            raise NMOSTestException(msg)

        time.sleep(2)

        active.assertActionCompleted(testRouteAction, retries=5)

        time.sleep(1)
