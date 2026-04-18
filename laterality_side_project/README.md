# Brain Laterality Side Project

In this side project, we used MUSE 2 headband and the Android app to record EEG data in three conditions:

1. ``rest``: Fixating a static image, resting task

2. ``language``: Engaged in foreign language understanding and guessing some easy vocabulary

3. ``emotional``: Emotional task: Listening to an emotional story

**All** are to be carried out with eyes open, fixating the resting image. The ``language`` and ``emotional`` conditions are complemented with listening to the respective stimuli and following the instructions in them (i.e. silently responding to the questions).



## Recording Notes

- Notes about individual participants are in ``data/notes.txt``.
- We used Muse2 + Niceboy headphones which somewhat helped to hold it in place
- We are a little worried if bluetooth was not interfering with the recording.


## Analaysis of Individual Participants

1. Open ``pdBSI_across_3_conditions.ipynb`` in you favourite Jupyter notebook.

2. In cell nr. 8 set ``participant`` to ``sample`` for the sample data, or to ``01``, ... for the individual participants.


You can see the file ``pdBSI_across_3_conditions.with_sample_outputs.pdf`` to see what it looks like without running the notebook.

## Analysis of All Participants at Once

Just run the analysis Python script on the console:

```
python pdBSI_across_3_conditions_with_quality_check.py
```

