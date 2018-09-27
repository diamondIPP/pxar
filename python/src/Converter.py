#!/usr/bin/env python
# --------------------------------------------------------
#       adds clustering and charge to trees created with pxar
# created on August 30th 2018 by M. Reichmann (remichae@phys.ethz.ch)
# --------------------------------------------------------

from ROOT import TFile, vector, TF1
from utils import *
from os.path import basename, join, dirname
from argparse import ArgumentParser
from collections import OrderedDict
from numpy import array, average
from progressbar import Bar, ETA, FileTransferSpeed, Percentage, ProgressBar
from pickle import load, dump
from draw import Draw, ufloat


class Converter:

    def __init__(self, filename):

        self.OldFile = read_root_file(filename)
        self.OldTree = self.OldFile.Get('Plane7').Get('Hits')
        self.NewFile = self.create_new_file(filename)
        self.NewTree = self.OldTree.CloneTree(0)

        # New Branches
        self.ScalarBranches = OrderedDict([('NCluster', array([0], 'u2'))])
        self.VectorBranches = OrderedDict([('VCal', vector('float')()),
                                           ('ClusterSize', vector('unsigned short')()),
                                           ('ClusterX', vector('float')()),
                                           ('ClusterY', vector('float')()),
                                           ('ClusterVcal', vector('float')())])

        # Charge Fits
        self.FitParameters = None
        self.Fit = TF1('ErFit', '[3] * (TMath::Erf((x - [0]) / [1]) + [2])', -500, 255 * 7)
        self.get_fit_data(filename)

        # Vars
        self.Hits = []
        self.ClusteredHits = []
        self.Clusters = []

        self.ProgressBar = None

    def start_pbar(self, n):
        self.ProgressBar = ProgressBar(widgets=['Progress: ', Percentage(), ' ', Bar(marker='>'), ' ', ETA(), ' ', FileTransferSpeed()], maxval=n)
        self.ProgressBar.start()

    @staticmethod
    def create_new_file(filename):
        nr = basename(filename).strip('.root').split('_')[-1]
        return TFile(join(dirname(filename), 'Clustered_{}.root'.format(nr)), 'RECREATE')

    def set_branches(self):
        for key, value in self.ScalarBranches.iteritems():
            self.NewTree.Branch(key, value, '{}/{}'.format(key, type_dict[value[0].dtype.name]))
        for key, vec in self.VectorBranches.iteritems():
            self.NewTree.Branch(key, vec)

    def clear_vectors(self):
        for key in self.VectorBranches.iterkeys():
            self.VectorBranches[key].clear()
        self.Clusters = []
        self.ClusteredHits = []
        self.Hits = []

    def get_fit_data(self, filename):
        pickle_name = 'fitpars.pickle'
        if file_exists(pickle_name):
            f = open(pickle_name, 'r')
            self.FitParameters = load(f)
            f.close()
        else:
            f = open(join(dirname(dirname(filename)), 'phCalibration_C0.dat'))
            f.readline()
            low_range = [int(val) for val in f.readline().split(':')[-1].split()]
            high_range = [int(val) for val in f.readline().split(':')[-1].split()]
            x = low_range + [val * 7 for val in high_range]
            f.readline()
            self.Fit.SetParameters(309.2062, 112.8961, 1.022439, 35.89524)
            d = Draw()
            self.start_pbar(52 * 80)
            for i, line in enumerate(f.readlines()):
                data = line.split('Pix')
                y = [int(val) for val in data[0].split()]
                x1 = [ufloat(ix, 1) for (ix, iy) in zip(x, y) if iy]
                y1 = [ufloat(iy, 1) for iy in y if iy]
                g = d.make_tgrapherrors('gcal', 'gcal', x=x1, y=y1)
                g.Fit(self.Fit, 'q', '', 0, 3000)
                col, row = [int(val) for val in data[-1].split()]
                self.FitParameters[col][row] = [self.Fit.GetParameter(i) for i in xrange(4)]
                self.ProgressBar.update(i + 1)
            self.ProgressBar.finish()
            fp = open(pickle_name, 'w')
            dump(self.FitParameters, fp)
            fp.close()
            f.close()

    def get_charge(self, col, row, adc):
        self.Fit.SetParameters(*self.FitParameters[col][row])
        return self.Fit.GetX(adc)

    def clusterise(self):
        for hit in self.Hits:
            if hit in self.ClusteredHits:
                continue
            cluster = Cluster()
            self.Clusters.append(cluster)
            cluster.add_hit(hit)
            self.ClusteredHits.append(hit)
            self.add_touching_hits(cluster, hit)

    def add_touching_hits(self, cluster, hit):
        for ihit in self.Hits:
            if ihit in self.ClusteredHits:
                continue
            if abs(ihit.X - hit.X) <= 2 and abs(ihit.Y - hit.Y) <= 2:
                cluster.add_hit(ihit)
                self.ClusteredHits.append(ihit)
                self.add_touching_hits(cluster, ihit)

    def run(self):
        self.set_branches()
        n = self.OldTree.GetEntries()
        self.start_pbar(n)
        for i, event in enumerate(self.OldTree):
            self.clear_vectors()
            x, y, adc = event.PixX, event.PixY, event.Value
            for ix, iy, iadc in zip(x, y, adc):
                hit = Hit(ix, iy)
                hit.set_charge(self.get_charge(ix, iy, iadc))
                self.VectorBranches['VCal'].push_back(hit.Charge)
                self.Hits.append(hit)
            self.clusterise()
            self.ScalarBranches['NCluster'][0] = len(self.Clusters)
            for cluster in self.Clusters:
                self.VectorBranches['ClusterSize'].push_back(cluster.size())
                self.VectorBranches['ClusterX'].push_back(cluster.x())
                self.VectorBranches['ClusterY'].push_back(cluster.y())
                self.VectorBranches['ClusterVcal'].push_back(cluster.charge())
            self.NewTree.Fill()
            self.ProgressBar.update(i + 1)
        self.ProgressBar.finish()
        self.NewFile.cd()
        self.NewFile.Write()
        self.NewFile.Close()


class Hit:

    def __init__(self, x, y):

        self.X = x
        self.Y = y

        self.Charge = None

    def set_charge(self, value):
        self.Charge = value

    def __str__(self):
        return 'Hit: {0} {1}, Charge: {2:1.2f}vcal'.format(self.X, self.Y, self.Charge)


class Cluster:

    def __init__(self):

        self.Hits = []

    def __str__(self):
        return 'Cluster of size {}, Charge: {}'.format(self.size(), self.charge())

    def add_hit(self, hit):
        self.Hits.append(hit)

    def size(self):
        return len(self.Hits)

    def charge(self):
        return sum(hit.Charge for hit in self.Hits)

    def seed_hit(self):
        return max(self.Hits, key=lambda hit: hit.Charge)

    def x(self):
        return average([hit.X for hit in self.Hits], weights=[hit.Charge for hit in self.Hits])

    def y(self):
        return average([hit.Y for hit in self.Hits], weights=[hit.Charge for hit in self.Hits])


if __name__ == '__main__':
    p = ArgumentParser()
    p.add_argument('filename')
    args = p.parse_args()
    z = Converter(args.filename)
    z.run()
