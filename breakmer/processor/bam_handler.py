#! /usr/bin/python
# -*- coding: utf-8 -*-

import pysam

__author__ = "Ryan Abo"
__copyright__ = "Copyright 2015, Ryan Abo"
__email__ = "ryanabo@gmail.com"
__license__ = "MIT"


def trim_qual(read, min_qual, min_len):
    qual_str = read.qual
    q = []
    coords = [0, len(qual_str)]
    start = seq_trim(qual_str, min_qual)
    if start == len(qual_str):
        return None
    else:
        end = len(qual_str) - seq_trim(qual_str[::-1], min_qual)
        lngth = end - start
        if lngth < min_len:
            return None
        nseq = read.seq[start:end]
        nqual = qual_str[start:end]
        read.seq = nseq
        read.qual = nqual
    return read


def fq_line(read, indel_only, min_len, trim=True):
    add_val = '0'
    if indel_only:
        add_val = '1'
    lineout = None
    if trim:
        read = trim_qual(read, 5, min_len)
    if read:
        lineout = "@" + get_seq_readname(read) + "_" + add_val + "\n" + read.seq + "\n+\n" + read.qual + "\n"
    return lineout


def get_seq_readname(read):
    """ """
    end = '1'
    if read.is_read2:
        end = '2'
    return read.qname + "/" + end


def check_pair_overlap(mate_seq, read, coords, trim_dir):
    """ """
    nmisses = 0
    add_clip = True
    clip_seq = read.seq[coords[0]:coords[1]]
    clip_len = coords[1] - coords[0]

    if abs(read.isize) < len(read.seq):
        if abs(len(read.seq) - (abs(read.isize) + 1)) >= clip_len:
            add_clip = False
    else:
        while check_overlap(trim_dir, mate_seq, clip_seq) and nmisses < 5 and len(clip_seq) > 0:
            if trim_dir == 'bacl':
                clip_seq = clip_seq[0:(len(clip_seq) - 1)]
            else:
                clip_seq = clip_seq[1:len(clip_seq)]
            nmisses += 1
        if len(clip_seq) == 0 or nmisses == 5:
            add_clip = True
        else:
            add_clip = False
    return add_clip


def check_overlap(dir, mate_seq, clip_seq):
    """ """
    if dir == 'back':
        return mate_seq.find(clip_seq) != (len(mate_seq) - len(clip_seq))
    else:
        return mate_seq.find(clip_seq) != 0


def get_clip_coords(read):
    """This will parse a cigar string for a read and determine the coordinates
    of the read that are not softclipped by the aligner.
    Args:
        read: pysam read object.
    Return:
        clip_coords: List with two integer values indicating the coordinates of
                     the sequence read that are not clipped.
    """

    # Read cigar is a list of tuples [(4,5),(0,80),(4,15)] 5 bp clipped in the start, 80 bp matching, 15 bp clipped at the end
    # Start: coords = [0,0]
    # Iter 1: coords = [5,5]
    # Iter 2: coords = [5,85]
    # Iter 3: coords = [5,85]

    clip_coords = [0, len(read.qual)]
    coords = [0, 0]
    for i in range(len(read.cigar)):
        code, clen = read.cigar[i]
        if not code == 2 and not code == 4:
            coords[1] += clen
        # Soft clipped code
        if code == 4:
            if i == 0:
                coords[0] = clen
                coords[1] += clen
        clip_coords = coords
    return clip_coords


def seq_trim(qual_str, min_qual):
    """Find the first position in a list of quality values that is above the minimum
    quality value input.
    Iterate over the list of quality values, starting at the first position, and
    return the position where the quality if greater than min_qual.
    Args:
        qual_str: List of quality values from pysam read object (i.e., read.qual).
                  These are Phred-based and assumed to be offset by 33.
        min_qual: Integer value of the minimum acceptable quality
    Return:
        counter: Integer representing the position in the list.
    """

    counter = 0
    while ord(qual_str[counter]) - 33 < min_qual:
        counter += 1
        if counter == len(qual_str):
            break
    return counter


def trim_coords(qual_str, min_qual):
    """Searches quality values of a sequence read start-end and end-start to
    determine if there is a sequence of bad quality sequences.
    Args:
        qual_str: List of quality values from pysam read object (i.e., read.qual).
                  These are Phred-based and assumed to be offset by 33.
        min_qual: Integer value of the minimum acceptable quality
    Return:
        three element tuple:
            1. position start where sequence quality is good (> min_qual)
            2. position end where sequence quality is good (> min_qual)
            3. length of the sequence that has good quality.
    """

    q = []
    coords = [0, len(qual_str)]
    start = seq_trim(qual_str, min_qual)
    if start == len(qual_str):
        return (0, 0, 0)
    else:
        end = len(qual_str) - seq_trim(qual_str[::-1], min_qual)
        lngth = end - start
        return (start, end, lngth)


def pe_meta(read):
    """Checks if the read is from a proper paired-end mapping, assuming an Illumina
       library.
       Args:
            read: pysam read object
        Return:
            proper_map: Boolean to indicate that the read-pair is properly mapped
            overlap_read: Boolean to indicate that the read-pair overlap (i.e.,
                          insert size < 2*read_len
    """

    proper_map = False
    overlap_reads = False
    if (((read.flag == 83 or read.flag == 147) and read.tlen < 0) or ((read.flag == 99 or read.flag == 163) and read.tlen > 0)):
        proper_map = True
        if abs(read.tlen) < (2 * len(read.seq)):
            overlap_reads = True
    return proper_map, overlap_reads


def get_region_reads(bamFile, chrom, start, end):
    """Open BAM file using pysam and fetch aligned reads in the
    specified region.
    Args:
        bamFile (str): Bam file full path, index must be in the same location
        chrom (str):    Chromosome name for region
        start (int):    Region's start position.
        end (int):      Region's end position.
    Return:
        reads (list): List containing pysam read objects
        bamF (pysam bam object): Open pysam bam file object.
    """

    bamF = pysam.Samfile(bamFile, 'rb')
    reads = bamF.fetch(chrom, start, end)
    return (reads, bamF)


def get_variant_reads(bamFile, chrom, start, end):
    """
    Args:
        bam_file: String of the path to the bam file to open, must be indexed!
        chrom: String of the chromosome of the region to extract
        start: Integer of the start location to extract.
        end: Integer of the end location to extract.
    Return:
        var_read_tracker: VarReadTracker object
    """
    reads, bamF = get_region_reads(bamFile, chrom, start, end)
    vrt = VariantReadTracker(bamF)
    for read in reads:
        skip = False
        if read.mate_is_unmapped or read.rnext == -1:
            read.mate_is_unmapped = True
        if read.is_duplicate or read.is_qcfail:
            skip = True
        if read.is_unmapped:
            vrt.add_unmapped_read(read)
            skip = True

        if skip:
            continue
        vrt.check_read(read)
    return vrt


class VariantReadTracker:
    """A class to track the reads that are identified to be 'misaligned' to
    the reference sequence.
    Attributes:
        pair_indices: Dictionary of a dictionary tracking the index of paired
                     reads in the valid list.
        valid: List of read objects that are valid to consider for extraction.
        disc: Dictionary of read IDs for read-pairs that are discordantly mapped.
        unmapped: Dictionary of unmapped reads with mapped mate in the region.
        unmapped_keep: List containing names of reads that are mapped but their mate is unmapped and wasn't
                       kept on the first pass.
        inv: List of tuples, each containing read-pair information that have alignments
             suggestive of an inversion event.
        td: List of tuples, each containing read-pair information that have alignments
            suggestive of a tandem dup event.
        other: List of tuples, each containing read-pair information that have alignments
               suggestive of some uncategorized event.
        sv: Dictionary
        bam: BAM file source the reads came from.
    """

    def __init__(self, bam_f):
        self.pair_indices = {}
        self.valid = []
        self.disc = {}
        self.unmapped = {}
        self.unmapped_keep = []
        self.inv = []
        self.td = []
        self.other = []
        self.sv = {}
        self.bam = bam_f

    def check_read(self, read):
        """ """

        # proper_map = False
        # overlapping_reads = False
        proper_map, overlapping_reads = pe_meta(read)
        if read.qname not in self.pair_indices and not read.mate_is_unmapped:
            self.add_discordant_pe(read)
        self.valid.append((read, proper_map, overlapping_reads))

        if read.qname not in self.pair_indices and not read.mate_is_unmapped:
            self.pair_indices[read.qname] = {}
        if read.qname in self.pair_indices:
            self.pair_indices[read.qname][int(read.is_read1)] = len(self.valid) - 1

    def add_unmapped_read(self, read):
        """Add read to unmapped dictionary with name as the key, object as the value"""
        self.unmapped[read.qname] = read

    def add_discordant_pe(self, read):
        """
        Args:
            read:
        Return:
            None
        """

        # Extract read-pairs that are mapped to different chromosomes or fair apart.
        diff_chroms = read.rnext != -1 and read.tid != read.rnext
        disc_ins_size = abs(read.tlen) >= 500
        if read.mapq > 0 and not read.mate_is_unmapped and (diff_chroms or disc_ins_size):
            mate_refid = self.bam.getrname(read.rnext)
            mate_read = self.bam.mate(read)
            if mate_read.mapq > 0:
                if mate_refid not in self.disc:
                    self.disc[mate_refid] = []
                self.disc[mate_refid].append((read.pos, read.pnext))

        if read.mapq > 0 and not read.mate_is_unmapped and read.tid == read.rnext:
            if read.is_read1:
                read_positions = None
                if read.is_reverse and read.mate_is_reverse:
                    # reverse -- reverse, samflag 115 (note: only considering read1, read2 samflag 179)
                    read_positions = (read.pos, read.mpos, 0, 0, read.qname)
                    if read.mpos < read.pos:
                        read_positions = (read.mpos, read.pos, 0, 0, read.qname)
                    self.inv.append(read_positions)
                elif not read.is_reverse and not read.mate_is_reverse:
                    # forward -- forward = samflag 67 (note: only considering read1, read2 samflag 131)
                    read_positions = (read.pos, read.mpos, 1, 1, read.qname)
                    if read.mpos < read.pos:
                        read_positions = (read.mpos, read.pos, 1, 1, read.qname)
                    self.inv.append(read_positions)
                elif read.is_reverse and not read.mate_is_reverse and read.pos < read.mpos:
                    # reverse -- forward = samflag 83 with positive insert (read2 samflag 163 with + insert size)
                    read_positions = (read.pos, read.mpos, 0, 1, read.qname)
                    self.td.append(read_positions)
                elif not read.is_reverse and read.mate_is_reverse and read.mpos < read.pos:
                    # reverse -- forward = samflag 99 with - insert (read2 samflag 147 with - insert)
                    read_positions = (read.mpos, read.pos, 1, 0, read.qname)
                    self.td.append(read_positions)
                if read_positions:
                    self.other.append(read_positions)

    def check_clippings(self, kmer_size, region_start_pos, region_end_pos):
        """
        """
        for read_vals in self.valid:
            read, proper_map, overlap_reads = read_vals
            if read.cigar or len(read.cigar) > 1:
                good_qual_coords = trim_coords(read.qual, 3)
                clip_coords = get_clip_coords(read)
                self.extract_clippings(read_vals, clip_coords, good_qual_coords, kmer_size)

            if (read.pos >= region_start_pos and read.pos <= region_end_pos) and read.mapq > 0 and read.mate_is_unmapped:
                self.unmapped_keep.append(read.qname)

    def extract_clippings(self, read_vals, clip_coords, good_qual_coords, kmer_size):
        """
        """

        read, proper_map, overlap_reads = read_vals
        clip_seqs = {'clipped': [], 'buffered': []}

        if clip_coords[0] <= good_qual_coords[0] and clip_coords[1] >= good_qual_coords[1]:
            return

        new_clip_coords = [0, 0]
        add_clip = [False, False]
        indel_only = False
        start_clip = clip_coords[0] > 0
        end_clip = clip_coords[1] < len(read.qual)
        if start_clip and end_clip:
            add_clip = [True, True]
        else:
            if start_clip:
                add_clip[0] = True
                new_clip_coords = [0, clip_coords[0]]
                if overlap_reads and read.is_reverse:
                    mate_seq = self.valid[self.pair_indices[read.qname][int(read.is_read1)]][0].seq
                    add_clip[0] = check_pair_overlap(mate_seq, read, [0, clip_coords[0]], 'back')
                if proper_map:
                    if read.is_reverse:
                        indel_only = True
                    else:
                        indel_only = False
            elif end_clip:
                new_clip_coords = [clip_coords[1], len(read.seq)]
                add_clip[1] = True
                if overlap_reads and not read.is_reverse:
                    mate_seq = self.valid[self.pair_indices[read.qname][int(read.is_read1)]][0].seq
                    add_clip[1] = check_pair_overlap(mate_seq, read, [clip_coords[1], len(read.seq)], 'front')
                if proper_map:
                    if read.is_reverse:
                        indel_only = indel_only and False
                    else:
                        indel_only = indel_only and True
        final_add = add_clip[0] or add_clip[1]
        if add_clip[0]:
            clip_seqs['buffered'].append(read.seq[0:(clip_coords[0] + kmer_size)])
            clip_seqs['clipped'].append(read.seq[0:clip_coords[0]])
        if add_clip[1]:
            clip_seqs['buffered'].append(read.seq[(clip_coords[1] - kmer_size):len(read.seq)])
            clip_seqs['clipped'].append(read.seq[clip_coords[1]:len(read.seq)])
        if final_add:
            self.sv[get_seq_readname(read)] = (read, clip_seqs, new_clip_coords, indel_only)

    def write_seqs(self, clipped_fa, reads_fq, sv_bam, kmer_size):
        """
        """

        for name in self.unmapped_keep:
            if name in self.unmapped:
                read = self.unmapped[name]
                self.sv[get_seq_readname(read)] = (read, None, None, False)
                lout = ">" + read.qname + "\n" + str(read.seq)
                clipped_fa.write(lout + "\n")

        for name in self.sv:
            read, clip_seqs, clip_coords, indel_only = self.sv[name]
            if sv_bam:
                sv_bam.write(read)
            lout = fq_line(read, indel_only, kmer_size, True)
            if lout:
                reads_fq.write(lout)
            if clip_seqs:
                for clip in clip_seqs['buffered']:
                    clipped_fa.write(">" + name + "\n" + clip + "\n")
        self.bam.close()

    def clear_sv_reads(self):
        self.sv = None