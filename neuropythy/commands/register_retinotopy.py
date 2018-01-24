####################################################################################################
# commands/register_retinotopy.py
# The code for the function that handles the registration of retinotopy
# By Noah C. Benson

from __future__ import print_function

import numpy                        as     np
import scipy                        as     sp
import nibabel                      as     nib
import nibabel.freesurfer.io        as     fsio
import nibabel.freesurfer.mghformat as     fsmgh
import pyrsistent                   as     pyr
import os, sys, six, pimms

from neuropythy.freesurfer          import (subject, add_subject_path)
from neuropythy.util                import CommandLineParser
from neuropythy.vision              import (register_retinotopy, retinotopy_model, clean_retinotopy,
                                            empirical_retinotopy_data)

info = \
   '''
   The register_retinotopy command can be used to register a subject's
   hemisphere(s) to a model of V1-V3. At least one  subject id (either a freesurfer
   subject name, if SUBJECTS_DIR is set appropriately in the environment, or a path
   to a subject directory) must be given. Registration to a retinotopic model of
   V1-V3 is performed for both hemispheres of all of these subjects.
   In each subject's freesurfer directory, a variety of output data is deposited:
    * surf/lh.retinotopy_sym.sphere.reg
      xhemi/surf/lh.retinotopy_sym.sphere.reg
      These files contain the registrations of the left and right hemispheres to
      the retinotopy model. They are in the same format as Freesurfer's other 
      surface-data files such as surf/lh.white.
    * surf/lh.angle_predict.mgz   surf/rh.angle_predict.mgz
      surf/lh.eccen_predict.mgz   surf/rh.eccen_predict.mgz
      surf/lh.varea_predict.mgz   surf/rh.varea_predict.mgz
      These files contain predictions of polar angle, eccentricity, and visual-area
      label for each hemisphere. The files are mgz format, so contain volumes;
      however, the volumes in each of these files is (1 x 1 x n) where n is the
      number of vertices in the hemisphere's Freesurfer meshes.
    * mri/angle_predict.mgz
      mri/eccen_predict.mgz
      mri/varea_predict.mgz
      These contain the data from the above surface data projected into the
      subject's 3D volume. Note that the volumes are oriented like Freesurfer's
      mri/brain.mgz file; if you want to convert this to the orientation of your
      original anatomical scan, use mri_convert:
       > mri_convert -rl mri/rawavg.mgz mri/angle_predict.mgz \\
                     mri/scanner.angle_predict.mgz
   The following options are accepted:
    * --eccen-lh=|-e<file>
      --angle-lh=|-a<file>
      --weight-lh=|-w<file>
      --eccen-rh=|-A<file>
      --angle-rh=|-E<file>
      --weight-rh=|-W<file>
      Each of these arguments specifies the name of a data file to load in as a
      representation of the subject's eccentricity, polar angle, or weight; these
      should be given the names of either an mgh/mgz files whose size is 1 x 1 x n,
      where n is the number of vertices in the hemisphere for the subject, or a
      FreeSurfer curv-style filename with n vertices. By default, files in the
      subject's surf directory that match a template are automatically loaded and
      used. This template is name <hemi>.<tag><name>, optionally ending with .mgz,
      where tag is one of (and in order of preference) 'prf_', 'empirical_',
      'measured_', 'training_', or '', and name is one of 'eccentricity'/'eccen',
      'polar_angle'/'angle', or 'weight'/'variance_explained'/'vexpl'.
    * --cutoff=|-c<value>
      The cutoff value to use for the weight; 0.1 by default. Weights less than
      this will be truncated to 0.
    * -N|--no-partial-correction
      Indicates that partial voluming correction should not be performed.
    * --angle-radians|-r
      This flag specifies that the angle-file only is in radians instead of
      degrees.
    * --eccen-radians|-R
      This flag specifies that the eccen-file only is in radians instead of
      degrees.
    * --mathematical|-m
      This flag specifies that the angle file addresses the visual space in the way
      standard in geometry; i.e., with the right horizontal meridian represented as
      0 and with the upper vertical meridian represented as 90 degrees or pi/4
      instead of the convention in which the opper vertical meridian represented as
      0 and the right horizontal meridian represented as 90 degrees or pi/4
      radians.
    * --edge-strength=|-D<weight>
      --angle-strength=|-T<weight>
      --functional-strength=|-F<weight>
      Each of these specifies the strength of the appropriate potential-field
      component. By default, these are each 1. Note that each field is already
      normalized by the number of components over which it operates; e.g., the edge
      strength is normalized by the number of edges in the mesh.
    * --max-steps=|-s<steps>
      This option specifies the maximum number of steps to run the registration; by
      default this is 2000.
    * --max-step-size=|-S<value>
      This specifies the max step-size for any single vertex; by default this is
      0.05.
    * --prior=|-p<name>
      This specifies the name of the prior registration to use in the fsaverage_sym
      subject; by default this is retinotopy. The prior may be omitted if the value
      "-" or "none" is given.
    * --eccen-tag=|-y<tag>
      --angle-tag=|-t<tag>
      --label-tag=|-l<tag>
      These options specify the output tag to use for the predicted measurement
      that results from the registration. By default, these are
      'eccen_predict', 'angle_predict', and 'varea_predict'.
      The output files have the name <hemi>.<tag>.mgz
    * --registration-name=|-u<string>
      This parameter indicates that the registration file, by default named 
      lh.retinotopy_sym.sphere.reg, should instead be named lh.<string>.sphere.reg.
    * --max-output-eccen=|-M<val>
      This specifies the maximum eccentricity to include in the output; there is no
      particular need to limit one's output, but it can be done with this argument.
      By default this is 90.
    * --no-volume-export|-x
      --no-surface-export|-z
      --no-registration-export|-X
      These flags indicate that the various data produced and written to the
      filesystem under normal execution should be suppressed. The volume export
      refers to the predicted volume files exported to the subject's mri directory;
      the registration export refers to the <hemi>.retinotopy_sym.sphere.reg file,
      written to the subject's surf directory, that contains the registered
      coordinates for the subject; and the surface export refers to the
      <hemi>.eccen_predict.mgz and similar files that are written to the
      subject's surf directory.
    * --subjects-dir=|-d
      Specifies additional subject directory search locations (in addition to the
      SUBJECTS_DIR environment variable and the FREESURFER_HOME/subjects
      directories, which are given here in descending search priority) when looking
      for subjects by name. This option cannot be specified multiple times, but it
      may contain : characters to separate directories, as in PATH.
    * --no-overwrite|-n
      This flag indicates that, when writing output files, no file should ever be
      replaced, should it already exist.
    * --
      This token, by itself, indicates that the arguments that remain should not be
      processed as flags or options, even if they begin with a -.
   '''
_retinotopy_parser_instructions = [
    # Flags
    ('h', 'help',                   'help',              False),
    ('v', 'verbose',                'verbose',           False),
    ('x', 'no-volume-export',       'no_vol_export',     False),
    ('z', 'no-surface-export',      'no_surf_export',    False),
    ('X', 'no-registration-export', 'no_reg_export',     False),
    ('n', 'no-overwrite',           'no_overwrite',      False),
    ('k', 'no-lh',                  'run_lh',            True),
    ('K', 'no-rh',                  'run_rh',            True),
    ('c', 'clean',                  'clean',             False),
    ('b', 'no-resample',            'resample',          True),
    ('N', 'partial-correction',     'part_vol_correct',  False),
    ('S', 'model-sym',              'model_sym',         False),
    ('V', 'invert-rh-angle',        'invert_rh_angle',   False),
    # Options
    ['a', 'lh-angle',               'angle_lh_file',     None],
    ['t', 'lh-theta',               'theta_lh_file',     None],
    ['e', 'lh-eccen',               'eccen_lh_file',     None],
    ['r', 'lh-rho',                 'rho_lh_file',       None],
    ['w', 'lh-weight',              'weight_lh_file',    None],
    ['q', 'lh-radius',              'radius_lh_file',    None],
    ['A', 'rh-angle',               'angle_rh_file',     None],
    ['T', 'rh-theta',               'theta_rh_file',     None],
    ['E', 'rh-eccen',               'eccen_rh_file',     None],
    ['R', 'rh-rho',                 'rho_rh_file',       None],
    ['W', 'rh-weight',              'weight_rh_file',    None],
    ['Q', 'rh-radius',              'radius_rh_file',    None],

    ['m', 'weight-min',             'weight_min',        '0.1'],
    ['s', 'scale',                  'scale',             '1.0'],
    ['g', 'field-sign-weight',      'field_sign_weight', '1.0'],
    ['G', 'radius-weight',          'radius_weight',     '1.0'],
    ['i', 'max-steps',              'max_steps',         '8000'],
    ['D', 'max-step-size',          'max_step_size',     '0.02'],
    ['p', 'prior',                  'prior',             None],

    ['f', 'surf-format',            'surface_format',    'curv'],
    ['F', 'vol-format',             'volume_format',     'mgz'],
    ['o', 'surf-outdir',            'surface_path',      None],
    ['o', 'vol-outdir',             'volume_path',       None],
    ['y', 'eccen-tag',              'eccen_tag',         'inferred_eccen'],
    ['w', 'angle-tag',              'angle_tag',         'inferred_angle'],
    ['l', 'label-tag',              'label_tag',         'inferred_varea'],
    ['j', 'radius-tag',             'radius_tag',        'inferred_sigma'],
    ['u', 'registration-name',      'registration_name', 'retinotopy'],
    ['M', 'max-output-eccen',       'max_out_eccen',     '90'],
    ['I', 'max-input-eccen',        'max_in_eccen',      '90'],
    ['J', 'min-input-eccen',        'min_in_eccen',      '0'],
    ['d', 'subjects-dir',           'subjects_dir',      None]]
_retinotopy_parser = CommandLineParser(_retinotopy_parser_instructions)

def _guess_surf_file(fl):
    # MGH/MGZ files
    try:    return fsmgh.load(fl).get_data().flatten()
    except: pass
    # FreeSurfer Curv files
    try:    return fsio.read_morph_data(fl)
    except: pass
    # Nifti files
    try:    return np.squeeze(nib.load(fl).get_data())
    except: raise ValueError('Could not determine filetype for: %s' % fl)
def _guess_vol_file(fl):
    # MGH/MGZ files
    try: return fsmgh.load(fl)
    except: pass
    # Nifti Files
    try: return nib.load(fl)
    except: raise ValueError('Could not determine filetype for: %s' % fl)

@pimms.calc('subject', 'model', 'options', 'note', 'error',
            'no_vol_export',     
            'no_surf_export',    
            'no_reg_export',     
            'no_overwrite',
            'model_sym',
            'invert_rh_angle',
            'part_vol_correct',  
            'angle_lh_file',     
            'theta_lh_file',     
            'eccen_lh_file',     
            'rho_lh_file',
            'run_lh',
            'weight_lh_file',
            'radius_lh_file',
            'angle_rh_file',     
            'theta_rh_file',     
            'eccen_rh_file',     
            'rho_rh_file',
            'run_rh',
            'clean',
            'weight_rh_file',
            'radius_rh_file',
            'weight_min',        
            'scale',             
            'max_steps',         
            'max_step_size',     
            'prior',             
            'surface_format',    
            'volume_format',     
            'surface_path',      
            'volume_path',       
            'eccen_tag',         
            'angle_tag',         
            'label_tag',
            'radius_tag',
            'registration_name', 
            'max_out_eccen',
            'max_in_eccen',
            'min_in_eccen',
            'resample',
            'field_sign_weight',
            'radius_weight')
def calc_arguments(args):
    '''
    calc_arguments is a calculator that parses the command-line arguments for the registration
    command and produces the subject, the model, the log function, and the additional options.
    '''
    (args, opts) = _retinotopy_parser(args)
    # We do some of the options right here...
    if opts['help']:
        print(info, file=sys.stdout)
        sys.exit(1)
    # and if we are verbose, lets setup a note function
    verbose = opts['verbose']
    def note(s):
        if verbose:
            print(s, file=sys.stdout)
            sys.stdout.flush()
        return verbose
    def error(s):
        print(s, file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)
    if len(args) < 1: error('subject argument is required')
    # Add the subjects directory, if there is one
    if 'subjects_dir' in opts and opts['subjects_dir'] is not None:
        add_subject_path(opts['subjects_dir'])
    # Get the subject now
    try: sub = subject(args[0])
    except: error('Failed to load subject %s' % args[0])
    # and the model
    if len(args) > 1:       mdl_name = args[1]
    elif opts['model_sym']: mdl_name = 'schira'
    else:                   mdl_name = 'benson17'
    try:
        if opts['model_sym']:
            model = {h:retinotopy_model(mdl_name).persist() for h in ['lh', 'rh']}
        else:
            model = {h:retinotopy_model(mdl_name, hemi=h).persist() for h in ['lh', 'rh']}
    except: error('Could not load retinotopy model %s' % mdl_name)

    # Now, we want to run a few filters on the options
    # Parse the simple numbers
    for o in ['weight_min', 'scale', 'max_step_size', 'max_out_eccen',
              'max_in_eccen', 'min_in_eccen', 'field_sign_weight', 'radius_weight']:
        opts[o] = float(opts[o])
    opts['max_steps'] = int(opts['max_steps'])
    # Make a note:
    note('Processing subject: %s' % sub.name)
    del opts['help']
    del opts['verbose']
    del opts['subjects_dir']
    # That's all we need!
    return pimms.merge(opts,
                       {'subject': sub.persist(),
                        'model':   pyr.pmap(model),
                        'options': pyr.pmap(opts),
                        'note':    note,
                        'error':   error})
@pimms.calc('cortices')
def calc_retinotopy(note, error, subject, clean, run_lh, run_rh,
                    invert_rh_angle, max_in_eccen, min_in_eccen,
                    angle_lh_file, theta_lh_file,
                    eccen_lh_file, rho_lh_file,
                    weight_lh_file, radius_lh_file,
                    angle_rh_file, theta_rh_file,
                    eccen_rh_file, rho_rh_file,
                    weight_rh_file, radius_rh_file):
    '''
    calc_retinotopy extracts the retinotopy options from the command line, loads the relevant files,
    and stores them as properties on the subject's lh and rh cortices.
    '''
    ctcs = {}
    for (h,ang,tht,ecc,rho,wgt,rad,run) in [
            ('lh', angle_lh_file,theta_lh_file, eccen_lh_file,rho_lh_file,
             weight_lh_file, radius_lh_file, run_lh),
            ('rh', angle_rh_file,theta_rh_file, eccen_rh_file,rho_rh_file,
             weight_rh_file, radius_rh_file, run_rh)]:
        if not run: continue
        hemi = getattr(subject, h)
        props = {}
        # load the properties or find them in the auto-properties
        if ang:
            try: props['polar_angle'] = _guess_surf_file(ang)
            except: error('could not load surface file %s' % ang)
        elif tht:
            try:
                tmp = _guess_surf_file(tht)
                props['polar_angle'] = 90.0 - 180.0 / np.pi * tmp
            except: error('could not load surface file %s' % tht)
        else:
            props['polar_angle'] = empirical_retinotopy_data(hemi, 'polar_angle')
        if ecc:
            try: props['eccentricity'] = _guess_surf_file(ecc)
            except: error('could not load surface file %s' % ecc)
        elif rho:
            try:
                tmp = _guess_surf_file(rhp)
                props['eccentricity'] = 180.0 / np.pi * tmp
            except: error('could not load surface file %s' % rho)
        else:
            props['eccentricity'] = empirical_retinotopy_data(hemi, 'eccentricity')
        if wgt:
            try: props['weight'] = _guess_surf_file(wgt)
            except: error('could not load surface file %s' % wgt)
        else:
            props['weight'] = empirical_retinotopy_data(hemi, 'weight')
        if rad:
            try: props['radius'] = _guess_surf_file(rad)
            except: error('could not load surface file %s' % rad)
        else:
            props['radius'] = empirical_retinotopy_data(hemi, 'radius')
        # Check for inverted rh
        if h == 'rh' and invert_rh_angle:
            props['polar_angle'] = -props['polar_angle']
        # and zero-out weights for high eccentricities
        if max_in_eccen is not None:
            props['weight'][props['eccentricity'] > max_in_eccen] = 0
        if min_in_eccen is not None:
            props['weight'][props['eccentricity'] < min_in_eccen] = 0
        # Do smoothing, if requested
        if clean:
            note('Cleaning %s retinotopy...' % h.upper())
            (ang,ecc) = clean_retinotopy(hemi, props)
            props['polar_angle']  = ang
            props['eccentricity'] = ecc
        ctcs[h] = hemi.with_prop(props)
    return {'cortices': pyr.pmap(ctcs)}
@pimms.calc('registrations')
def calc_registrations(note, error, cortices, model, model_sym,
                       weight_min, scale, prior, max_out_eccen, max_steps, max_step_size,
                       radius_weight, field_sign_weight, resample, invert_rh_angle,
                       part_vol_correct):
    '''
    calc_registrations is the calculator that performs the registrations for the left and right
    hemisphere; these are returned as the immutable maps yielded from the register_retinotopy
    command.
    '''
    rsamp = ('fsaverage_sym' if model_sym else 'fsaverage') if resample else False
    # Do the registration
    res = {}
    for (h,ctx) in six.iteritems(cortices):
        note('Preparing %s Registration...' % h.upper())
        try:
            res[h] = register_retinotopy(ctx, model[h],
                                         model_hemi='sym' if model_sym else h,
                                         polar_angle='polar_angle',
                                         eccentricity='eccentricity',
                                         weight='weight',
                                         weight_min=weight_min,
                                         partial_voluming_correction=part_vol_correct,
                                         field_sign_weight=field_sign_weight,
                                         radius_weight=radius_weight,
                                         scale=scale,
                                         prior=prior,
                                         resample=rsamp,
                                         invert_rh_field_sign=invert_rh_angle,
                                         max_steps=max_steps,
                                         max_step_size=max_step_size,
                                         yield_imap=True)
        except: #error('Exception caught while setting-up register_retinotopy (%s)' % h)
            raise
    return {'registrations': pyr.pmap(res)}
@pimms.calc('surface_files')
def save_surface_files(note, error, registrations, subject,
                       no_surf_export, no_reg_export, surface_format, surface_path,
                       angle_tag, eccen_tag, label_tag, radius_tag, registration_name):
    '''
    save_surface_files is the calculator that saves the registration data out as surface files,
    which are put back in the registration as the value 'surface_files'.
    '''
    if no_surf_export: return {'surface_files': ()}
    surface_format = surface_format.lower()
    # make an exporter for properties:
    if surface_format in ['curv', 'morph', 'auto', 'automatic']:
        def export(flnm, p):
            with open(flnm, 'w') as fl: fsio.write_morph_data(fl, p)
            return flnm
    elif surface_format in ['mgh', 'mgz']:
        def export(flnm, p):
            flnm = flnm + '.' + surface_format
            dt = np.int32 if np.issubdtype(p.dtype, np.int) else np.float32
            img = fsmgh.MGHImage(np.asarray([[p]], dtype=dt), np.eye(4))
            img.to_filename(flnm)
            return flnm
    elif surface_format in ['nifti', 'nii', 'niigz', 'nii.gz']:
        surface_format = 'nii' if surface_format == 'nii' else 'nii.gz'
        def export(flnm, p):
            flnm = flnm + '.' + surface_format
            dt = np.int32 if np.issubdtype(p.dtype, np.int) else np.float32
            img = nib.Nifti1Image(np.asarray([[p]], dtype=dt), np.eye(4))
            img.to_filename(flnm)
            return flnm
    else:
        error('Could not understand surface file-format %s' % surface_format)
    path = surface_path if surface_path else os.path.join(subject.path, 'surf')
    files = []
    note('Exporting files...')
    for h in six.iterkeys(registrations):
        hemi = getattr(subject, h)
        reg = registrations[h]
        note('Extracting %s predicted mesh...' % h.upper())
        pmesh = reg['predicted_mesh']
        for (pname,tag) in zip(['polar_angle', 'eccentricity', 'visual_area', 'radius'],
                               [angle_tag, eccen_tag, label_tag, radius_tag]):
            flnm = export(os.path.join(path, h + '.' + tag), pmesh.prop(pname))
            files.append(flnm)
        # last do the registration itself
        if registration_name and not no_reg_export:
            flnm = os.path.join(path, h + '.' + registration_name + '.sphere.reg')
            fsio.write_geometry(flnm, pmesh.coordinates.T, pmesh.tess.faces.T)
    return {'surface_files': tuple(files)}
@pimms.calc('volume_files')
def save_volume_files(note, error, registrations, subject,
                      no_vol_export, volume_format, volume_path,
                      angle_tag, eccen_tag, label_tag, radius_tag):
    '''
    save_volume_files is the calculator that saves the registration data out as volume files,
    which are put back in the registration as the value 'volume_files'.
    '''
    if no_vol_export: return {'volume_files': ()}
    volume_format = volume_format.lower()
    # make an exporter for properties:
    if volume_format in ['mgh', 'mgz', 'auto', 'automatic', 'default']:
        volume_format = 'mgh' if volume_format == 'mgh' else 'mgz'
        def export(flnm, d):
            flnm = flnm + '.' + volume_format
            dt = np.int32 if np.issubdtype(d.dtype, np.int) else np.float32
            img = fsmgh.MGHImage(np.asarray(d, dtype=dt), subject.voxel_to_vertex_matrix)
            img.to_filename(flnm)
            return flnm
    elif volume_format in ['nifti', 'nii', 'niigz', 'nii.gz']:
        volume_format = 'nii' if volume_format == 'nii' else 'nii.gz'
        def export(flnm, p):
            flnm = flnm + '.' + volume_format
            dt = np.int32 if np.issubdtype(p.dtype, np.int) else np.float32
            img = nib.Nifti1Image(np.asarray(p, dtype=dt), subject.voxel_to_vertex_matrix)
            img.to_filename(flnm)
            return flnm
    else:
        error('Could not understand volume file-format %s' % volume_format)
    path = volume_path if volume_path else os.path.join(subject.path, 'mri')
    files = []
    note('Extracting predicted meshes for volume export...')
    hemis = [registrations[h]['predicted_mesh'] if h in registrations else None
             for h in ['lh', 'rh']]
    for (pname,tag) in zip(['polar_angle', 'eccentricity', 'visual_area', 'radius'],
                           [angle_tag, eccen_tag, label_tag, radius_tag]):
        # we have to make the volume first...
        dat = tuple([None if h is None else h.prop(pname) for h in hemis])
        (mtd,dt) = ('nearest',np.int32) if pname == 'visual_area' else ('linear',np.float32)
        note('Constructing %s image...' % pname)
        img = subject.cortex_to_image(dat, method=mtd, dtype=dt)
        flnm = export(os.path.join(path, tag), img)
        files.append(flnm)
    return {'volume_files': tuple(files)}
@pimms.calc('files')
def accumulate_files(surface_files, volume_files):
    '''
    accumulate_files is a calculator that just accumulates the exported files into a single tuple,
    files.
    '''
    return {'files': (tuple(surface_files) + tuple(volume_files))}

register_retinotopy_plan = pimms.plan(args=calc_arguments,
                                      retinotopy=calc_retinotopy,
                                      register=calc_registrations,
                                      surf_export=save_surface_files,
                                      vol_export=save_volume_files,
                                      accum_files=accumulate_files)

def main(args):
    '''
    register_retinotopy.main(args) can be given a list of arguments, such as sys.argv[1:]; these
    arguments may include any options and must include at least one subject id. All subjects whose
    ids are given are registered to a retinotopy model, and the resulting registration, as well as
    the predictions made by the model in the registration, are exported.
    '''
    m = register_retinotopy_plan(args=args)
    # force completion
    files = m['files']
    if len(files) > 0:
        return 0
    else:
        print('Error: No files exported.', file=sys.stderr)
        return 1

