#!/usr/bin/env python
# --------------------------------------------------------
#       Class to write a list is pXar Events into a root tree
# created on February 20th 2017 by M. Reichmann (remichae@phys.ethz.ch)
# --------------------------------------------------------

from ROOT import TTree, TFile, vector
from progressbar import Bar, ETA, FileTransferSpeed, Percentage, ProgressBar
from numpy import array
from collections import OrderedDict


class TreeWriter:

    def __init__(self, data):

        self.Data = data
        self.File = None
        self.Tree = None
        self.VectorBranches = self.init_vector_branches()
        self.ScalarBranches = self.init_scalar_branches()

        self.ProgressBar = None

    def start_pbar(self, n):
        self.ProgressBar = ProgressBar(widgets=['Progress: ', Percentage(), ' ', Bar(marker='>'), ' ', ETA(), ' ', FileTransferSpeed()], maxval=n)
        self.ProgressBar.start()

    @staticmethod
    def init_vector_branches():
        dic = OrderedDict([('plane', vector('unsigned short')()),
                           ('col', vector('unsigned short')()),
                           ('row', vector('unsigned short')()),
                           ('adc', vector('short')()),
                           ('header', vector('unsigned int')()),
                           ('trailer', vector('unsigned int')()),
                           ('pkam', vector('unsigned short')()),
                           ('token_pass', vector('unsigned short')()),
                           ('reset_tbm', vector('unsigned short')()),
                           ('reset_roc', vector('unsigned short')()),
                           ('auto_reset', vector('unsigned short')()),
                           ('cal_trigger', vector('unsigned short')()),
                           ('trigger_count', vector('unsigned short')()),
                           ('trigger_phase', vector('unsigned short')()),
                           ('stack_count', vector('unsigned short')())])
        return dic

    @staticmethod
    def init_scalar_branches():
        dic = {'incomplete_data': array([0], 'ushort'),
               'missing_roc_headers': array([0], 'ushort'),
               'roc_readback': array([0], 'ushort'),
               'invalid_addresses': array([0], 'ushort'),
               'invalid_pulse_heights': array([0], 'ushort'),
               'buffer_corruptions': array([0], 'ushort')}
        return dic

    def clear_vectors(self):
        for key in self.VectorBranches.iterkeys():
            self.VectorBranches[key].clear()

    def set_branches(self):
        for key, vec in self.VectorBranches.iteritems():
            self.Tree.Branch(key, vec)
        for key, branch in self.ScalarBranches.iteritems():
            self.Tree.Branch(key, branch, '{k}/s'.format(k=key))

    def write_tree(self, hv, cur):
        hv_str = '-{v}'.format(v=hv) if hv is not None else ''
        cur_str = '-{c}'.format(c=cur) if cur is not None else ''
        self.File = TFile('run{v}{c}.root'.format(v=hv_str, c=cur_str), 'RECREATE')
        self.Tree = TTree('tree', 'The error tree')
        self.set_branches()
        self.start_pbar(len(self.Data))
        for i, ev in enumerate(self.Data):
            self.ProgressBar.update(i + 1)
            self.clear_vectors()
            for pix in ev.pixels:
                self.VectorBranches['plane'].push_back(int(pix.roc))
                self.VectorBranches['col'].push_back(int(pix.column))
                self.VectorBranches['row'].push_back(int(pix.row))
                self.VectorBranches['adc'].push_back(int(pix.value))
            for j in xrange(len(ev.header)):
                self.VectorBranches['header'].push_back(ev.header[j])
                self.VectorBranches['trailer'].push_back(ev.trailer[j])
                self.VectorBranches['pkam'].push_back(ev.havePkamReset[j])
                self.VectorBranches['cal_trigger'].push_back(ev.haveCalTrigger[j])
                self.VectorBranches['token_pass'].push_back(ev.haveTokenPass[j])
                self.VectorBranches['reset_tbm'].push_back(ev.haveResetTBM[j])
                self.VectorBranches['reset_roc'].push_back(ev.haveResetROC[j])
                self.VectorBranches['auto_reset'].push_back(ev.haveAutoReset[j])
                self.VectorBranches['trigger_count'].push_back(ev.triggerCounts[j])
                self.VectorBranches['trigger_phase'].push_back(ev.triggerPhases[j])
                self.VectorBranches['stack_count'].push_back(ev.stackCounts[j])
            self.ScalarBranches['incomplete_data'][0] = ev.incomplete_data
            self.ScalarBranches['missing_roc_headers'][0] = ev.missing_roc_headers
            self.ScalarBranches['roc_readback'][0] = ev.roc_readback
            self.ScalarBranches['invalid_addresses'][0] = ev.invalid_addresses
            self.ScalarBranches['invalid_pulse_heights'][0] = ev.invalid_pulse_heights
            self.ScalarBranches['buffer_corruptions'][0] = ev.buffer_corruptions
            self.Tree.Fill()
        self.ProgressBar.finish()
        self.File.cd()
        self.File.Write()
        self.File.Close()
