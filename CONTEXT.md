# Conf T

An interactive trainer for practicing command-line skills. Learners either follow a curriculum path or drill commands they need to see again.

## Language

### Modes

**Practice**:
The mode in which a learner works through a lesson on the curriculum path.
_Avoid_: tutorial, course, study session

**Review**:
The mode in which a learner drills tasks they have already seen and need to see again.
_Avoid_: exam, quiz, assessment

A change serves Practice, Review, or both. Shared lessons stay valid for both modes. Neither mode is dropped to favor the other.

### Curriculum

**Platform**:
A command environment the lessons simulate. The current set is Cisco, Linux, PowerShell, Git, and Docker.
_Avoid_: track, module, subject

**Lesson**:
An ordered set of tasks on one topic, belonging to one platform.
_Avoid_: chapter, lab, module

**Task**:
One complete command the learner is asked to produce, with a prompt and an accepted answer; a complete shell compound command also counts. Each task supplies its own scenario so it can be answered independently in Practice or Review.
_Avoid_: question, exercise, step

**Hint**:
Help the learner can ask for while a task is still unanswered. It may include the command.
_Avoid_: explanation

**Explanation**:
What the learner reads after answering, covering why that command is the right one.
_Avoid_: hint

### People

**Learner**:
A person using Conf T. Two situations are in scope: a student following a path, and a working admin brushing up. Neither situation outranks the other.
_Avoid_: user, student (as the only audience), operator
