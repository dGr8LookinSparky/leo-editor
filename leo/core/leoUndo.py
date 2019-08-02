#@+leo-ver=5-thin
#@+node:ekr.20031218072017.3603: * @file leoUndo.py
'''Leo's undo/redo manager.'''
#@+<< How Leo implements unlimited undo >>
#@+node:ekr.20031218072017.2413: ** << How Leo implements unlimited undo >>
#@+at Think of the actions that may be Undone or Redone as a string of beads
# (g.Bunches) containing all information needed to undo _and_ redo an operation.
# 
# A bead pointer points to the present bead. Undoing an operation moves the bead
# pointer backwards; redoing an operation moves the bead pointer forwards. The
# bead pointer points in front of the first bead when Undo is disabled. The bead
# pointer points at the last bead when Redo is disabled.
# 
# The Undo command uses the present bead to undo the action, then moves the bead
# pointer backwards. The Redo command uses the bead after the present bead to redo
# the action, then moves the bead pointer forwards. The list of beads does not
# branch; all undoable operations (except the Undo and Redo commands themselves)
# delete any beads following the newly created bead.
# 
# New in Leo 4.3: User (client) code should call u.beforeX and u.afterX methods to
# create a bead describing the operation that is being performed. (By convention,
# the code sets u = c.undoer for undoable operations.) Most u.beforeX methods
# return 'undoData' that the client code merely passes to the corresponding
# u.afterX method. This data contains the 'before' snapshot. The u.afterX methods
# then create a bead containing both the 'before' and 'after' snapshots.
# 
# New in Leo 4.3: u.beforeChangeGroup and u.afterChangeGroup allow multiple calls
# to u.beforeX and u.afterX methods to be treated as a single undoable entry. See
# the code for the Replace All, Sort, Promote and Demote commands for examples.
# u.before/afterChangeGroup substantially reduce the number of u.before/afterX
# methods needed.
# 
# New in Leo 4.3: It would be possible for plugins or other code to define their
# own u.before/afterX methods. Indeed, u.afterX merely needs to set the
# bunch.undoHelper and bunch.redoHelper ivars to the methods used to undo and redo
# the operation. See the code for the various u.before/afterX methods for
# guidance.
# 
# New in Leo 4.3: p.setDirty and p.setAllAncestorAtFileNodesDirty now return a
# 'dirtyVnodeList' that all vnodes that became dirty as the result of an
# operation. More than one list may be generated: client code is responsible for
# merging lists using the pattern dirtyVnodeList.extend(dirtyVnodeList2)
# 
# I first saw this model of unlimited undo in the documentation for Apple's Yellow Box classes.
#@-<< How Leo implements unlimited undo >>
import leo.core.leoGlobals as g
# pylint: disable=unpacking-non-sequence
#@+others
#@+node:ekr.20031218072017.3605: ** class Undoer
class Undoer:
    """A class that implements unlimited undo and redo."""
    # pylint: disable=not-an-iterable
    # pylint: disable=unsubscriptable-object
    # So that ivars can be inited to None rather thatn [].
    #@+others
    #@+node:ekr.20150509193307.1: *3* u.Birth
    #@+node:ekr.20031218072017.3606: *4* u.__init__ & reloadSettings
    def __init__(self, c):
        self.c = c
        self.debug_Undoer = False # True: enable debugging code in new undo scheme.
        self.debug_print = False # True: enable print statements in debug code.
        self.granularity = None # Set in reloadSettings.
        self.max_undo_stack_size = c.config.getInt('max-undo-stack-size') or 0
        # Statistics comparing old and new ways (only if self.debug_Undoer is on).
        self.new_mem = 0
        self.old_mem = 0
        # State ivars...
        self.beads = [] # List of undo nodes.
        self.bead = -1 # Index of the present bead: -1:len(beads)
        self.undoType = "Can't Undo"
        # These must be set here, _not_ in clearUndoState.
        self.redoMenuLabel = "Can't Redo"
        self.undoMenuLabel = "Can't Undo"
        self.realRedoMenuLabel = "Can't Redo"
        self.realUndoMenuLabel = "Can't Undo"
        self.undoing = False # True if executing an Undo command.
        self.redoing = False # True if executing a Redo command.
        self.per_node_undo = False # True: v may contain undo_info ivar.
        # New in 4.2...
        self.optionalIvars = []
        # Set the following ivars to keep pylint happy.
        self.afterTree = None
        self.beforeTree = None
        self.children = None
        self.deleteMarkedNodesData = None
        self.dirtyVnodeList = None
        self.followingSibs = None
        self.inHead = None
        self.kind = None
        self.newBack = None
        self.newBody = None
        self.newChanged = None
        self.newChildren = None
        self.newHead = None
        self.newMarked = None
        self.newN = None
        self.newP = None
        self.newParent = None
        self.newParent_v = None
        self.newRecentFiles = None
        self.newSel = None
        self.newTree = None
        self.newYScroll = None
        self.oldBack = None
        self.oldBody = None
        self.oldChanged = None
        self.oldChildren = None
        self.oldHead = None
        self.oldMarked = None
        self.oldN = None
        self.oldParent = None
        self.oldParent_v = None
        self.oldRecentFiles = None
        self.oldSel = None
        self.oldTree = None
        self.oldYScroll = None
        self.pasteAsClone = None
        self.prevSel = None
        self.sortChildren = None
        self.verboseUndoGroup = None
        self.reloadSettings()
        
    def reloadSettings(self):
        '''Undoer.reloadSettings.'''
        c = self.c
        self.granularity = c.config.getString('undo-granularity')
        if self.granularity:
            self.granularity = self.granularity.lower()
        if self.granularity not in ('node', 'line', 'word', 'char'):
            self.granularity = 'line'

    def redoHelper(self):
        pass

    def undoHelper(self):
        pass
    #@+node:ekr.20150509193222.1: *4* u.cmd (decorator)
    def cmd(name):
        '''Command decorator for the Undoer class.'''
        # pylint: disable=no-self-argument
        return g.new_cmd_decorator(name, ['c', 'undoer', ])
    #@+node:ekr.20050416092908.1: *3* u.Internal helpers
    #@+node:ekr.20031218072017.3607: *4* u.clearOptionalIvars
    def clearOptionalIvars(self):
        u = self
        u.p = None # The position/node being operated upon for undo and redo.
        for ivar in u.optionalIvars:
            setattr(u, ivar, None)
    #@+node:ekr.20060127052111.1: *4* u.cutStack
    def cutStack(self):
        u = self; n = u.max_undo_stack_size
        if u.bead >= n > 0 and not g.app.unitTesting:
            # Do nothing if we are in the middle of creating a group.
            i = len(u.beads) - 1
            while i >= 0:
                bunch = u.beads[i]
                if hasattr(bunch, 'kind') and bunch.kind == 'beforeGroup':
                    return
                i -= 1
            # This work regardless of how many items appear after bead n.
                # g.trace('Cutting undo stack to %d entries' % (n))
            u.beads = u.beads[-n:]
            u.bead = n - 1
    #@+node:ekr.20080623083646.10: *4* u.dumpBead
    def dumpBead(self, n):
        u = self
        if n < 0 or n >= len(u.beads):
            return 'no bead: n = ', n
        # bunch = u.beads[n]
        result = []
        result.append('-' * 10)
        result.append('len(u.beads): %s, n: %s' % (len(u.beads), n))
        for ivar in ('kind', 'newP', 'newN', 'p', 'oldN', 'undoHelper'):
            result.append('%s = %s' % (ivar, getattr(self, ivar)))
        return '\n'.join(result)

    def dumpTopBead(self):
        u = self
        n = len(u.beads)
        if n > 0:
            return self.dumpBead(n - 1)
        return '<no top bead>'
    #@+node:EKR.20040526150818: *4* u.getBead
    def getBead(self, n):
        '''Set Undoer ivars from the bunch at the top of the undo stack.'''
        u = self
        if n < 0 or n >= len(u.beads):
            return None
        bunch = u.beads[n]
        self.setIvarsFromBunch(bunch)
        return bunch
    #@+node:EKR.20040526150818.1: *4* u.peekBead
    def peekBead(self, n):

        u = self
        if n < 0 or n >= len(u.beads):
            return None
        return u.beads[n]
    #@+node:ekr.20060127113243: *4* u.pushBead
    def pushBead(self, bunch):
        u = self
        # New in 4.4b2:  Add this to the group if it is being accumulated.
        bunch2 = u.bead >= 0 and u.bead < len(u.beads) and u.beads[u.bead]
        if bunch2 and hasattr(bunch2, 'kind') and bunch2.kind == 'beforeGroup':
            # Just append the new bunch the group's items.
            bunch2.items.append(bunch)
        else:
            # Push the bunch.
            u.bead += 1
            u.beads[u.bead:] = [bunch]
            # Recalculate the menu labels.
            u.setUndoTypes()
    #@+node:ekr.20050126081529: *4* u.recognizeStartOfTypingWord
    def recognizeStartOfTypingWord(self,
        old_lines, old_row, old_col, old_ch,
        new_lines, new_row, new_col, new_ch,
        prev_row, prev_col
    ):
        ''' A potentially user-modifiable method that should return True if the
        typing indicated by the params starts a new 'word' for the purposes of
        undo with 'word' granularity.

        u.setUndoTypingParams calls this method only when the typing could possibly
        continue a previous word. In other words, undo will work safely regardless
        of the value returned here.

        old_ch is the char at the given (Tk) row, col of old_lines.
        new_ch is the char at the given (Tk) row, col of new_lines.

        The present code uses only old_ch and new_ch. The other arguments are given
        for use by more sophisticated algorithms.'''
        # Start a word if new_ch begins whitespace + word
        new_word_started = not old_ch.isspace() and new_ch.isspace()
        # Start a word if the cursor has been moved since the last change
        moved_cursor = new_row != prev_row or new_col != prev_col + 1
        return new_word_started or moved_cursor
    #@+node:ekr.20031218072017.3613: *4* u.redoMenuName, undoMenuName
    def redoMenuName(self, name):
        if name == "Can't Redo":
            return name
        return "Redo " + name

    def undoMenuName(self, name):
        if name == "Can't Undo":
            return name
        return "Undo " + name
    #@+node:ekr.20060127070008: *4* u.setIvarsFromBunch
    def setIvarsFromBunch(self, bunch):
        u = self
        u.clearOptionalIvars()
        if 0: # Debugging.
            g.pr('-' * 40)
            for key in sorted(bunch):
                g.trace(key, bunch.get(key))
            g.pr('-' * 20)
        # bunch is not a dict, so bunch.keys() is required.
        for key in list(bunch.keys()):
            val = bunch.get(key)
            setattr(u, key, val)
            if key not in u.optionalIvars:
                u.optionalIvars.append(key)
    #@+node:ekr.20031218072017.3614: *4* u.setRedoType
    # These routines update both the ivar and the menu label.

    def setRedoType(self, theType):

        u = self; frame = u.c.frame
        if not isinstance(theType, str):
            g.trace('oops: expected string for command, got %s' % repr(theType))
            g.trace(g.callers())
            theType = '<unknown>'
        menu = frame.menu.getMenu("Edit")
        name = u.redoMenuName(theType)
        if name != u.redoMenuLabel:
            # Update menu using old name.
            realLabel = frame.menu.getRealMenuName(name)
            if realLabel == name:
                underline = -1 if g.match(name, 0, "Can't") else 0
            else:
                underline = realLabel.find("&")
            realLabel = realLabel.replace("&", "")
            frame.menu.setMenuLabel(menu, u.realRedoMenuLabel, realLabel, underline=underline)
            u.redoMenuLabel = name
            u.realRedoMenuLabel = realLabel
    #@+node:ekr.20091221145433.6381: *4* u.setUndoType
    def setUndoType(self, theType):

        u = self; frame = u.c.frame
        if not isinstance(theType, str):
            g.trace('oops: expected string for command, got %s' % repr(theType))
            g.trace(g.callers())
            theType = '<unknown>'
        menu = frame.menu.getMenu("Edit")
        name = u.undoMenuName(theType)
        if name != u.undoMenuLabel:
            # Update menu using old name.
            realLabel = frame.menu.getRealMenuName(name)
            if realLabel == name:
                underline = -1 if g.match(name, 0, "Can't") else 0
            else:
                underline = realLabel.find("&")
            realLabel = realLabel.replace("&", "")
            frame.menu.setMenuLabel(menu, u.realUndoMenuLabel, realLabel, underline=underline)
            u.undoType = theType
            u.undoMenuLabel = name
            u.realUndoMenuLabel = realLabel
    #@+node:ekr.20031218072017.3616: *4* u.setUndoTypes
    def setUndoTypes(self):

        u = self
        # Set the undo type and undo menu label.
        bunch = u.peekBead(u.bead)
        if bunch:
            u.setUndoType(bunch.undoType)
        else:
            u.setUndoType("Can't Undo")
        # Set only the redo menu label.
        bunch = u.peekBead(u.bead + 1)
        if bunch:
            u.setRedoType(bunch.undoType)
        else:
            u.setRedoType("Can't Redo")
        u.cutStack()
    #@+node:EKR.20040530121329: *4* u.restoreTree & helpers
    def restoreTree(self, treeInfo):
        """Use the tree info to restore all VNode data,
        including all links."""
        u = self
        # This effectively relinks all vnodes.
        for v, vInfo, tInfo in treeInfo:
            u.restoreVnodeUndoInfo(vInfo)
            u.restoreTnodeUndoInfo(tInfo)
    #@+node:ekr.20050415170737.2: *5* u.restoreVnodeUndoInfo
    def restoreVnodeUndoInfo(self, bunch):
        """Restore all ivars saved in the bunch."""
        v = bunch.v
        v.statusBits = bunch.statusBits
        v.children = bunch.children
        v.parents = bunch.parents
        uA = bunch.get('unknownAttributes')
        if uA is not None:
            v.unknownAttributes = uA
            v._p_changed = 1
    #@+node:ekr.20050415170812.2: *5* u.restoreTnodeUndoInfo
    def restoreTnodeUndoInfo(self, bunch):
        v = bunch.v
        v.h = bunch.headString
        v.b = bunch.bodyString
        v.statusBits = bunch.statusBits
        uA = bunch.get('unknownAttributes')
        if uA is not None:
            v.unknownAttributes = uA
            v._p_changed = 1
    #@+node:EKR.20040528075307: *4* u.saveTree & helpers
    def saveTree(self, p, treeInfo=None):
        """Return a list of tuples with all info needed to handle a general undo operation."""
        # WARNING: read this before doing anything "clever"
        #@+<< about u.saveTree >>
        #@+node:EKR.20040530114124: *5* << about u.saveTree >>
        #@+at The old code made a free-standing copy of the tree using v.copy and
        # t.copy. This looks "elegant" and is WRONG. The problem is that it can
        # not handle clones properly, especially when some clones were in the
        # "undo" tree and some were not. Moreover, it required complex
        # adjustments to t.vnodeLists.
        # 
        # Instead of creating new nodes, the new code creates all information
        # needed to properly restore the vnodes and tnodes. It creates a list of
        # tuples, on tuple for each VNode in the tree. Each tuple has the form,
        # 
        # (vnodeInfo, tnodeInfo)
        # 
        # where vnodeInfo and tnodeInfo are dicts contain all info needed to
        # recreate the nodes. The v.createUndoInfoDict and t.createUndoInfoDict
        # methods correspond to the old v.copy and t.copy methods.
        # 
        # Aside: Prior to 4.2 Leo used a scheme that was equivalent to the
        # createUndoInfoDict info, but quite a bit uglier.
        #@-<< about u.saveTree >>
        u = self; topLevel = (treeInfo is None)
        if topLevel: treeInfo = []
        # Add info for p.v.  Duplicate tnode info is harmless.
        data = (p.v, u.createVnodeUndoInfo(p.v), u.createTnodeUndoInfo(p.v))
        treeInfo.append(data)
        # Recursively add info for the subtree.
        child = p.firstChild()
        while child:
            self.saveTree(child, treeInfo)
            child = child.next()
        return treeInfo
    #@+node:ekr.20050415170737.1: *5* u.createVnodeUndoInfo
    def createVnodeUndoInfo(self, v):
        """Create a bunch containing all info needed to recreate a VNode for undo."""
        bunch = g.Bunch(
            v=v,
            statusBits=v.statusBits,
            parents=v.parents[:],
            children=v.children[:],
        )
        if hasattr(v, 'unknownAttributes'):
            bunch.unknownAttributes = v.unknownAttributes
        return bunch
    #@+node:ekr.20050415170812.1: *5* u.createTnodeUndoInfo
    def createTnodeUndoInfo(self, v):
        """Create a bunch containing all info needed to recreate a VNode."""
        bunch = g.Bunch(
            v=v,
            headString=v.h,
            bodyString=v.b,
            statusBits=v.statusBits,
        )
        if hasattr(v, 'unknownAttributes'):
            bunch.unknownAttributes = v.unknownAttributes
        return bunch
    #@+node:ekr.20050525151449: *4* u.trace
    def trace(self):
        ivars = ('kind', 'undoType')
        for ivar in ivars:
            g.pr(ivar, getattr(self, ivar))
    #@+node:ekr.20050410095424: *4* u.updateMarks
    def updateMarks(self, oldOrNew):
        '''Update dirty and marked bits.'''
        u = self; c = u.c
        if oldOrNew not in ('new', 'old'):
            g.trace("can't happen")
            return
        isOld = oldOrNew == 'old'
        marked = u.oldMarked if isOld else u.newMarked
        if marked: c.setMarked(u.p)
        else: c.clearMarked(u.p)
        # Bug fix: Leo 4.4.6: Undo/redo always set changed/dirty bits
        # because the file may have been saved.
        u.p.setDirty(setDescendentsDirty=False)
        u.p.setAllAncestorAtFileNodesDirty(setDescendentsDirty=False) # Bug fix: Leo 4.4.6
        u.c.setChanged(True)
    #@+node:ekr.20031218072017.3608: *3* u.Externally visible entries
    #@+node:ekr.20050318085432.4: *4* u.afterX...
    #@+node:ekr.20050315134017.4: *5* u.afterChangeGroup
    def afterChangeGroup(self, p, undoType, reportFlag=False, dirtyVnodeList=None):
        '''Create an undo node for general tree operations using d created by beforeChangeGroup'''
        u = self; c = self.c
        w = c.frame.body.wrapper
        if u.redoing or u.undoing:
            return
        if dirtyVnodeList is None: dirtyVnodeList = []
        bunch = u.beads[u.bead]
        if not u.beads:
            g.trace('oops: empty undo stack.')
            return
        if bunch.kind == 'beforeGroup':
            bunch.kind = 'afterGroup'
        else:
            g.trace('oops: expecting beforeGroup, got %s' % bunch.kind)
        # Set the types & helpers.
        bunch.kind = 'afterGroup'
        bunch.undoType = undoType
        # Set helper only for undo:
        # The bead pointer will point to an 'beforeGroup' bead for redo.
        bunch.undoHelper = u.undoGroup
        bunch.redoHelper = u.redoGroup
        bunch.dirtyVnodeList = dirtyVnodeList
        bunch.newP = p.copy()
        bunch.newSel = w.getSelectionRange()
        # Tells whether to report the number of separate changes undone/redone.
        bunch.reportFlag = reportFlag
        if 0:
            # Push the bunch.
            u.bead += 1
            u.beads[u.bead:] = [bunch]
        # Recalculate the menu labels.
        u.setUndoTypes()
    #@+node:ekr.20050315134017.2: *5* u.afterChangeNodeContents
    def afterChangeNodeContents(self, p, command, bunch, dirtyVnodeList=None, inHead=False):
        '''Create an undo node using d created by beforeChangeNode.'''
        u = self; c = self.c; w = c.frame.body.wrapper
        if u.redoing or u.undoing:
            return
        if dirtyVnodeList is None: dirtyVnodeList = []
        # Set the type & helpers.
        bunch.kind = 'node'
        bunch.undoType = command
        bunch.undoHelper = u.undoNodeContents
        bunch.redoHelper = u.redoNodeContents
        bunch.dirtyVnodeList = dirtyVnodeList
        bunch.inHead = inHead # 2013/08/26
        bunch.newBody = p.b
        bunch.newChanged = u.c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newHead = p.h
        bunch.newMarked = p.isMarked()
        # Bug fix 2017/11/12: don't use ternary operator.
        if w:
            bunch.newSel = w.getSelectionRange()
        else:
            bunch.newSel = 0, 0
        bunch.newYScroll = w.getYScrollPosition() if w else 0
        u.pushBead(bunch)
    #@+node:ekr.20050315134017.3: *5* u.afterChangeTree
    def afterChangeTree(self, p, command, bunch):
        '''Create an undo node for general tree operations using d created by beforeChangeTree'''
        u = self; c = self.c; w = c.frame.body.wrapper
        if u.redoing or u.undoing: return
        # Set the types & helpers.
        bunch.kind = 'tree'
        bunch.undoType = command
        bunch.undoHelper = u.undoTree
        bunch.redoHelper = u.redoTree
        # Set by beforeChangeTree: changed, oldSel, oldText, oldTree, p
        bunch.newSel = w.getSelectionRange()
        bunch.newText = w.getAllText()
        bunch.newTree = u.saveTree(p)
        u.pushBead(bunch)
    #@+node:ekr.20050424161505: *5* u.afterClearRecentFiles
    def afterClearRecentFiles(self, bunch):
        u = self
        bunch.newRecentFiles = g.app.config.recentFiles[:]
        bunch.undoType = 'Clear Recent Files'
        bunch.undoHelper = u.undoClearRecentFiles
        bunch.redoHelper = u.redoClearRecentFiles
        u.pushBead(bunch)
        return bunch
    #@+node:ekr.20111006060936.15639: *5* u.afterCloneMarkedNodes
    def afterCloneMarkedNodes(self, p):
        u = self; c = u.c
        if u.redoing or u.undoing:
            return
        bunch = u.createCommonBunch(p)
            # Sets
            # oldChanged = c.isChanged(),
            # oldDirty = p.isDirty(),
            # oldMarked = p.isMarked(),
            # oldSel = w and w.getSelectionRange() or None,
            # p = p.copy(),
        # Set types & helpers
        bunch.kind = 'clone-marked-nodes'
        bunch.undoType = 'clone-marked-nodes'
        # Set helpers
        bunch.undoHelper = u.undoCloneMarkedNodes
        bunch.redoHelper = u.redoCloneMarkedNodes
        bunch.newP = p.next()
        bunch.newChanged = c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        u.pushBead(bunch)
    #@+node:ekr.20160502175451.1: *5* u.afterCopyMarkedNodes
    def afterCopyMarkedNodes(self, p):
        u = self; c = u.c
        if u.redoing or u.undoing:
            return
        bunch = u.createCommonBunch(p)
            # Sets
            # oldChanged = c.isChanged(),
            # oldDirty = p.isDirty(),
            # oldMarked = p.isMarked(),
            # oldSel = w and w.getSelectionRange() or None,
            # p = p.copy(),
        # Set types & helpers
        bunch.kind = 'copy-marked-nodes'
        bunch.undoType = 'copy-marked-nodes'
        # Set helpers
        bunch.undoHelper = u.undoCopyMarkedNodes
        bunch.redoHelper = u.redoCopyMarkedNodes
        bunch.newP = p.next()
        bunch.newChanged = c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        u.pushBead(bunch)
    #@+node:ekr.20050411193627.5: *5* u.afterCloneNode
    def afterCloneNode(self, p, command, bunch, dirtyVnodeList=None):
        u = self; c = u.c
        if u.redoing or u.undoing: return
        if dirtyVnodeList is None: dirtyVnodeList = []
        # Set types & helpers
        bunch.kind = 'clone'
        bunch.undoType = command
        # Set helpers
        bunch.undoHelper = u.undoCloneNode
        bunch.redoHelper = u.redoCloneNode
        bunch.newBack = p.back() # 6/15/05
        bunch.newParent = p.parent() # 6/15/05
        bunch.newP = p.copy()
        bunch.dirtyVnodeList = dirtyVnodeList
        bunch.newChanged = c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        u.pushBead(bunch)
    #@+node:ekr.20050411193627.6: *5* u.afterDehoist
    def afterDehoist(self, p, command):
        u = self
        if u.redoing or u.undoing: return
        bunch = u.createCommonBunch(p)
        # Set types & helpers
        bunch.kind = 'dehoist'
        bunch.undoType = command
        # Set helpers
        bunch.undoHelper = u.undoDehoistNode
        bunch.redoHelper = u.redoDehoistNode
        u.pushBead(bunch)
    #@+node:ekr.20050411193627.8: *5* u.afterDeleteNode
    def afterDeleteNode(self, p, command, bunch, dirtyVnodeList=None):
        u = self; c = u.c
        if u.redoing or u.undoing:
            return
        if dirtyVnodeList is None: dirtyVnodeList = []
        # Set types & helpers
        bunch.kind = 'delete'
        bunch.undoType = command
        # Set helpers
        bunch.undoHelper = u.undoDeleteNode
        bunch.redoHelper = u.redoDeleteNode
        bunch.newP = p.copy()
        bunch.dirtyVnodeList = dirtyVnodeList
        bunch.newChanged = c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        u.pushBead(bunch)
    #@+node:ekr.20111005152227.15555: *5* u.afterDeleteMarkedNodes
    def afterDeleteMarkedNodes(self, data, p):
        u = self; c = u.c
        if u.redoing or u.undoing: return
        bunch = u.createCommonBunch(p)
        # Set types & helpers
        bunch.kind = 'delete-marked-nodes'
        bunch.undoType = 'delete-marked-nodes'
        # Set helpers
        bunch.undoHelper = u.undoDeleteMarkedNodes
        bunch.redoHelper = u.redoDeleteMarkedNodes
        bunch.newP = p.copy()
        bunch.deleteMarkedNodesData = data
        # bunch.dirtyVnodeList = dirtyVnodeList
        bunch.newChanged = c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        u.pushBead(bunch)
    #@+node:ekr.20080425060424.8: *5* u.afterDemote
    def afterDemote(self, p, followingSibs, dirtyVnodeList):
        '''Create an undo node for demote operations.'''
        u = self
        bunch = u.createCommonBunch(p)
        # Set types.
        bunch.kind = 'demote'
        bunch.undoType = 'Demote'
        bunch.undoHelper = u.undoDemote
        bunch.redoHelper = u.redoDemote
        bunch.followingSibs = followingSibs
        # Push the bunch.
        u.bead += 1
        u.beads[u.bead:] = [bunch]
        # Recalculate the menu labels.
        u.setUndoTypes()
    #@+node:ekr.20050411193627.7: *5* u.afterHoist
    def afterHoist(self, p, command):
        u = self
        if u.redoing or u.undoing:
            return
        bunch = u.createCommonBunch(p)
        # Set types & helpers
        bunch.kind = 'hoist'
        bunch.undoType = command
        # Set helpers
        bunch.undoHelper = u.undoHoistNode
        bunch.redoHelper = u.redoHoistNode
        u.pushBead(bunch)
    #@+node:ekr.20050411193627.9: *5* u.afterInsertNode
    def afterInsertNode(self, p, command, bunch, dirtyVnodeList=None):
        u = self; c = u.c
        if u.redoing or u.undoing:
            return
        if dirtyVnodeList is None: dirtyVnodeList = []
        # Set types & helpers
        bunch.kind = 'insert'
        bunch.undoType = command
        # Set helpers
        bunch.undoHelper = u.undoInsertNode
        bunch.redoHelper = u.redoInsertNode
        bunch.newP = p.copy()
        bunch.dirtyVnodeList = dirtyVnodeList
        bunch.newBack = p.back()
        bunch.newParent = p.parent()
        bunch.newChanged = c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        if bunch.pasteAsClone:
            beforeTree = bunch.beforeTree
            afterTree = []
            for bunch2 in beforeTree:
                v = bunch2.v
                afterTree.append(
                    g.Bunch(v=v, head=v.h[:], body=v.b[:]))
            bunch.afterTree = afterTree
        u.pushBead(bunch)
    #@+node:ekr.20050526124257: *5* u.afterMark
    def afterMark(self, p, command, bunch, dirtyVnodeList=None):
        '''Create an undo node for mark and unmark commands.'''
        # 'command' unused, but present for compatibility with similar methods.
        u = self
        if u.redoing or u.undoing: return
        if dirtyVnodeList is None: dirtyVnodeList = []
        # Set the type & helpers.
        bunch.undoHelper = u.undoMark
        bunch.redoHelper = u.redoMark
        bunch.dirtyVnodeList = dirtyVnodeList
        bunch.newChanged = u.c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        u.pushBead(bunch)
    #@+node:ekr.20050410110343: *5* u.afterMoveNode
    def afterMoveNode(self, p, command, bunch, dirtyVnodeList=None):
        u = self; c = u.c
        if u.redoing or u.undoing: return
        if dirtyVnodeList is None: dirtyVnodeList = []
        # Set the types & helpers.
        bunch.kind = 'move'
        bunch.undoType = command
        # Set helper only for undo:
        # The bead pointer will point to an 'beforeGroup' bead for redo.
        bunch.undoHelper = u.undoMove
        bunch.redoHelper = u.redoMove
        bunch.dirtyVnodeList = dirtyVnodeList
        bunch.newChanged = c.isChanged()
        bunch.newDirty = p.isDirty()
        bunch.newMarked = p.isMarked()
        bunch.newN = p.childIndex()
        bunch.newParent_v = p._parentVnode()
        bunch.newP = p.copy()
        u.pushBead(bunch)
    #@+node:ekr.20080425060424.12: *5* u.afterPromote
    def afterPromote(self, p, children, dirtyVnodeList):
        '''Create an undo node for demote operations.'''
        u = self
        bunch = u.createCommonBunch(p)
        # Set types.
        bunch.kind = 'promote'
        bunch.undoType = 'Promote'
        bunch.undoHelper = u.undoPromote
        bunch.redoHelper = u.redoPromote
        bunch.children = children
        # Push the bunch.
        u.bead += 1
        u.beads[u.bead:] = [bunch]
        # Recalculate the menu labels.
        u.setUndoTypes()
    #@+node:ekr.20080425060424.2: *5* u.afterSort
    def afterSort(self, p, bunch, dirtyVnodeList):
        '''Create an undo node for sort operations'''
        u = self
        # c = self.c
        if u.redoing or u.undoing: return
        bunch.dirtyVnodeList = dirtyVnodeList
        # Recalculate the menu labels.
        u.setUndoTypes()

    #@+node:ekr.20050318085432.3: *4* u.beforeX...
    #@+node:ekr.20050315134017.7: *5* u.beforeChangeGroup
    def beforeChangeGroup(self, p, command, verboseUndoGroup=True):
        '''Prepare to undo a group of undoable operations.'''
        u = self
        bunch = u.createCommonBunch(p)
        # Set types.
        bunch.kind = 'beforeGroup'
        bunch.undoType = command
        bunch.verboseUndoGroup = verboseUndoGroup
        # Set helper only for redo:
        # The bead pointer will point to an 'afterGroup' bead for undo.
        bunch.undoHelper = u.undoGroup
        bunch.redoHelper = u.redoGroup
        bunch.items = []
        # Push the bunch.
        u.bead += 1
        u.beads[u.bead:] = [bunch]
    #@+node:ekr.20050315133212.2: *5* u.beforeChangeNodeContents
    def beforeChangeNodeContents(self, p, oldBody=None, oldHead=None, oldYScroll=None):
        '''Return data that gets passed to afterChangeNode'''
        u = self
        bunch = u.createCommonBunch(p)
        bunch.oldBody = oldBody or p.b
        bunch.oldHead = oldHead or p.h
        bunch.oldYScroll = oldYScroll
        return bunch
    #@+node:ekr.20050315134017.6: *5* u.beforeChangeTree
    def beforeChangeTree(self, p):
        u = self; c = u.c
        w = c.frame.body.wrapper
        bunch = u.createCommonBunch(p)
        bunch.oldSel = w.getSelectionRange()
        bunch.oldText = w.getAllText()
        bunch.oldTree = u.saveTree(p)
        return bunch
    #@+node:ekr.20050424161505.1: *5* u.beforeClearRecentFiles
    def beforeClearRecentFiles(self):
        u = self; p = u.c.p
        bunch = u.createCommonBunch(p)
        bunch.oldRecentFiles = g.app.config.recentFiles[:]
        return bunch
    #@+node:ekr.20050412080354: *5* u.beforeCloneNode
    def beforeCloneNode(self, p):
        u = self
        bunch = u.createCommonBunch(p)
        return bunch
    #@+node:ekr.20050411193627.3: *5* u.beforeDeleteNode
    def beforeDeleteNode(self, p):
        u = self
        bunch = u.createCommonBunch(p)
        bunch.oldBack = p.back()
        bunch.oldParent = p.parent()
        return bunch
    #@+node:ekr.20050411193627.4: *5* u.beforeInsertNode
    def beforeInsertNode(self, p, pasteAsClone=False, copiedBunchList=None):
        u = self
        if copiedBunchList is None: copiedBunchList = []
        bunch = u.createCommonBunch(p)
        bunch.pasteAsClone = pasteAsClone
        if pasteAsClone:
            # Save the list of bunched.
            bunch.beforeTree = copiedBunchList
        return bunch
    #@+node:ekr.20050526131252: *5* u.beforeMark
    def beforeMark(self, p, command):
        u = self
        bunch = u.createCommonBunch(p)
        bunch.kind = 'mark'
        bunch.undoType = command
        return bunch
    #@+node:ekr.20050410110215: *5* u.beforeMoveNode
    def beforeMoveNode(self, p):
        u = self
        bunch = u.createCommonBunch(p)
        bunch.oldN = p.childIndex()
        bunch.oldParent_v = p._parentVnode()
        return bunch
    #@+node:ekr.20080425060424.3: *5* u.beforeSort
    def beforeSort(self, p, undoType, oldChildren, newChildren, sortChildren):
        '''Create an undo node for sort operations.'''
        u = self
        bunch = u.createCommonBunch(p)
        # Set types.
        bunch.kind = 'sort'
        bunch.undoType = undoType
        bunch.undoHelper = u.undoSort
        bunch.redoHelper = u.redoSort
        bunch.oldChildren = oldChildren
        bunch.newChildren = newChildren
        bunch.sortChildren = sortChildren # A bool
        # Push the bunch.
        u.bead += 1
        u.beads[u.bead:] = [bunch]
        return bunch
    #@+node:ekr.20050318085432.2: *5* u.createCommonBunch
    def createCommonBunch(self, p):
        '''Return a bunch containing all common undo info.
        This is mostly the info for recreating an empty node at position p.'''
        u = self; c = u.c; w = c.frame.body.wrapper
        return g.Bunch(
            oldChanged=c.isChanged(),
            oldDirty=p and p.isDirty(),
            oldMarked=p and p.isMarked(),
            oldSel=w and w.getSelectionRange() or None,
            p=p and p.copy(),
        )
    #@+node:ekr.20031218072017.3610: *4* u.canRedo & canUndo
    # Translation does not affect these routines.

    def canRedo(self):
        u = self
        return u.redoMenuLabel != "Can't Redo"

    def canUndo(self):
        u = self
        return u.undoMenuLabel != "Can't Undo"
    #@+node:ekr.20031218072017.3609: *4* u.clearUndoState
    def clearUndoState(self):
        """Clears then entire Undo state.

        All non-undoable commands should call this method."""
        u = self
        u.clearOptionalIvars() # Do this first.
        u.setRedoType("Can't Redo")
        u.setUndoType("Can't Undo")
        u.beads = [] # List of undo nodes.
        u.bead = -1 # Index of the present bead: -1:len(beads)
    #@+node:ekr.20031218072017.3611: *4* u.enableMenuItems
    def enableMenuItems(self):
        u = self; frame = u.c.frame
        menu = frame.menu.getMenu("Edit")
        if menu:
            frame.menu.enableMenu(menu, u.redoMenuLabel, u.canRedo())
            frame.menu.enableMenu(menu, u.undoMenuLabel, u.canUndo())
    #@+node:ekr.20110519074734.6094: *4* u.onSelect & helpers
    def onSelect(self, old_p, p):

        u = self
        if u.per_node_undo:
            if old_p and u.beads:
                u.putIvarsToVnode(old_p)
            u.setIvarsFromVnode(p)
            u.setUndoTypes()
    #@+node:ekr.20110519074734.6096: *5* u.putIvarsToVnode
    def putIvarsToVnode(self, p):

        u = self; v = p.v
        assert self.per_node_undo
        bunch = g.bunch()
        for key in self.optionalIvars:
            bunch[key] = getattr(u, key)
        # Put these ivars by hand.
        for key in ('bead', 'beads', 'undoType',):
            bunch[key] = getattr(u, key)
        v.undo_info = bunch
    #@+node:ekr.20110519074734.6095: *5* u.setIvarsFromVnode
    def setIvarsFromVnode(self, p):
        u = self; v = p.v
        assert self.per_node_undo
        u.clearUndoState()
        if hasattr(v, 'undo_info'):
            u.setIvarsFromBunch(v.undo_info)
    #@+node:ekr.20031218072017.1490: *4* u.setUndoTypingParams
    def setUndoTypingParams(self, p, undo_type, oldText, newText,
        oldSel=None, newSel=None, oldYview=None,
    ):
        '''
        Save enough information to undo or redo typing operation.

        Do nothing when called from the undo/redo logic because the Undo
        and Redo commands merely reset the bead pointer.
        '''
        u = self; c = u.c
        #@+<< return if there is nothing to do >>
        #@+node:ekr.20040324061854: *5* << return if there is nothing to do >>
        if u.redoing or u.undoing:
            return None
        if undo_type is None:
            return None
        if undo_type == "Can't Undo":
            u.clearUndoState()
            u.setUndoTypes() # Must still recalculate the menu labels.
            return None
        if oldText == newText:
            u.setUndoTypes() # Must still recalculate the menu labels.
            return None
        #@-<< return if there is nothing to do >>
        #@+<< init the undo params >>
        #@+node:ekr.20040324061854.1: *5* << init the undo params >>
        # Clear all optional params.
        # for ivar in u.optionalIvars:
            # setattr(u,ivar,None)
        u.clearOptionalIvars()
        # Set the params.
        u.undoType = undo_type
        u.p = p.copy()
        #@-<< init the undo params >>
        #@+<< compute leading, middle & trailing  lines >>
        #@+node:ekr.20031218072017.1491: *5* << compute leading, middle & trailing  lines >>
        #@+at Incremental undo typing is similar to incremental syntax coloring. We compute
        # the number of leading and trailing lines that match, and save both the old and
        # new middle lines. NB: the number of old and new middle lines may be different.
        #@@c
        old_lines = oldText.split('\n')
        new_lines = newText.split('\n')
        new_len = len(new_lines)
        old_len = len(old_lines)
        min_len = min(old_len, new_len)
        i = 0
        while i < min_len:
            if old_lines[i] != new_lines[i]:
                break
            i += 1
        leading = i
        if leading == new_len:
            # This happens when we remove lines from the end.
            # The new text is simply the leading lines from the old text.
            trailing = 0
        else:
            i = 0
            while i < min_len - leading:
                if old_lines[old_len - i - 1] != new_lines[new_len - i - 1]:
                    break
                i += 1
            trailing = i
        # NB: the number of old and new middle lines may be different.
        if trailing == 0:
            old_middle_lines = old_lines[leading:]
            new_middle_lines = new_lines[leading:]
        else:
            old_middle_lines = old_lines[leading: -trailing]
            new_middle_lines = new_lines[leading: -trailing]
        # Remember how many trailing newlines in the old and new text.
        i = len(oldText) - 1; old_newlines = 0
        while i >= 0 and oldText[i] == '\n':
            old_newlines += 1
            i -= 1
        i = len(newText) - 1; new_newlines = 0
        while i >= 0 and newText[i] == '\n':
            new_newlines += 1
            i -= 1
        #@-<< compute leading, middle & trailing  lines >>
        #@+<< save undo text info >>
        #@+node:ekr.20031218072017.1492: *5* << save undo text info >>
        #@+at This is the start of the incremental undo algorithm.
        # 
        # We must save enough info to do _both_ of the following:
        # 
        # Undo: Given newText, recreate oldText.
        # Redo: Given oldText, recreate oldText.
        # 
        # The "given" texts for the undo and redo routines are simply p.b.
        #@@c
        if u.debug_Undoer:
            # Remember the complete text for comparisons...
            u.oldText = oldText
            u.newText = newText
            # Compute statistics comparing old and new ways...
            # The old doesn't often store the old text, so don't count it here.
            u.old_mem += len(newText)
            s1 = '\n'.join(old_middle_lines)
            s2 = '\n'.join(new_middle_lines)
            u.new_mem += len(s1) + len(s2)
        else:
            u.oldText = None
            u.newText = None
        u.leading = leading
        u.trailing = trailing
        u.oldMiddleLines = old_middle_lines
        u.newMiddleLines = new_middle_lines
        u.oldNewlines = old_newlines
        u.newNewlines = new_newlines
        #@-<< save undo text info >>
        #@+<< save the selection and scrolling position >>
        #@+node:ekr.20040324061854.2: *5* << save the selection and scrolling position >>
        # Remember the selection.
        u.oldSel = oldSel
        u.newSel = newSel
        # Remember the scrolling position.
        if oldYview:
            u.yview = oldYview
        else:
            u.yview = c.frame.body.wrapper.getYScrollPosition()
        #@-<< save the selection and scrolling position >>
        #@+<< adjust the undo stack, clearing all forward entries >>
        #@+node:ekr.20040324061854.3: *5* << adjust the undo stack, clearing all forward entries >>
        #@+at New in Leo 4.3. Instead of creating a new bead on every character, we
        # may adjust the top bead:
        # 
        # word granularity: adjust the top bead if the typing would continue the word.
        # line granularity: adjust the top bead if the typing is on the same line.
        # node granularity: adjust the top bead if the typing is anywhere on the same node.
        #@@c
        granularity = u.granularity
        old_d = u.peekBead(u.bead)
        old_p = old_d and old_d.get('p')
        #@+<< set newBead if we can't share the previous bead >>
        #@+node:ekr.20050125220613: *6* << set newBead if we can't share the previous bead >>
        #@+at We must set newBead to True if undo_type is not 'Typing' so that commands that
        # get treated like typing (by updateBodyPane and onBodyChanged) don't get lumped
        # with 'real' typing.
        #@@c
        if (
            not old_d or not old_p or
            old_p.v != p.v or
            old_d.get('kind') != 'typing' or
            old_d.get('undoType') != 'Typing' or
            undo_type != 'Typing'
        ):
            newBead = True # We can't share the previous node.
        elif granularity == 'char':
            newBead = True # This was the old way.
        elif granularity == 'node':
            newBead = False # Always replace previous bead.
        else:
            assert granularity in ('line', 'word')
            # Replace the previous bead if only the middle lines have changed.
            newBead = (
                old_d.get('leading', 0) != u.leading or
                old_d.get('trailing', 0) != u.trailing
            )
            if granularity == 'word' and not newBead:
                # Protect the method that may be changed by the user
                try:
                    #@+<< set newBead if the change does not continue a word >>
                    #@+node:ekr.20050125203937: *7* << set newBead if the change does not continue a word >>
                    # Fix #653: undoer problem: be wary of the ternary operator here.
                    old_start = old_end = new_start = new_end = 0
                    if oldSel:
                        old_start, old_end = oldSel
                    if newSel:
                        new_start, new_end = newSel
                    prev_start, prev_end = u.prevSel
                    if old_start != old_end or new_start != new_end:
                        # The new and old characters are not contiguous.
                        newBead = True
                    else:
                        # 2011/04/01: Patch by Sam Hartsfield
                        old_row, old_col = g.convertPythonIndexToRowCol(oldText, old_start)
                        new_row, new_col = g.convertPythonIndexToRowCol(newText, new_start)
                        prev_row, prev_col = g.convertPythonIndexToRowCol(oldText, prev_start)
                        old_lines = g.splitLines(oldText)
                        new_lines = g.splitLines(newText)
                        # Recognize backspace, del, etc. as contiguous.
                        if old_row != new_row or abs(old_col - new_col) != 1:
                            # The new and old characters are not contiguous.
                            newBead = True
                        elif old_col == 0 or new_col == 0:
                            # py-lint: disable=W0511
                            # W0511:1362: TODO
                            # TODO this is not true, we might as well just have entered a
                            # char at the beginning of an existing line
                            pass # We have just inserted a line.
                        else:
                            # 2011/04/01: Patch by Sam Hartsfield
                            old_s = old_lines[old_row]
                            new_s = new_lines[new_row]
                            # New in 4.3b2:
                            # Guard against invalid oldSel or newSel params.
                            if old_col - 1 >= len(old_s) or new_col - 1 >= len(new_s):
                                newBead = True
                            else:
                                old_ch = old_s[old_col - 1]
                                new_ch = new_s[new_col - 1]
                                newBead = self.recognizeStartOfTypingWord(
                                    old_lines, old_row, old_col, old_ch,
                                    new_lines, new_row, new_col, new_ch,
                                    prev_row, prev_col)
                    #@-<< set newBead if the change does not continue a word >>
                except Exception:
                    g.error('Unexpected exception...')
                    g.es_exception()
                    newBead = True
        #@-<< set newBead if we can't share the previous bead >>
        # Save end selection as new "previous" selection
        u.prevSel = u.newSel
        if newBead:
            # Push params on undo stack, clearing all forward entries.
            bunch = g.Bunch(
                p=p.copy(),
                kind='typing',
                undoType=undo_type,
                undoHelper=u.undoTyping,
                redoHelper=u.redoTyping,
                oldText=u.oldText,
                oldSel=u.oldSel,
                oldNewlines=u.oldNewlines,
                oldMiddleLines=u.oldMiddleLines,
            )
            u.pushBead(bunch)
        else:
            bunch = old_d
        bunch.dirtyVnodeList = p.setAllAncestorAtFileNodesDirty()
        # Bug fix: Leo 4.4.6: always add p to the list.
        bunch.dirtyVnodeList.append(p.copy())
        bunch.leading = u.leading
        bunch.trailing = u.trailing
        bunch.newNewlines = u.newNewlines
        bunch.newMiddleLines = u.newMiddleLines
        bunch.newSel = u.newSel
        bunch.newText = u.newText
        bunch.yview = u.yview
        #@-<< adjust the undo stack, clearing all forward entries >>
        if u.per_node_undo:
            u.putIvarsToVnode(p)
        return bunch # Never used.
    #@+node:ekr.20031218072017.2030: *3* u.redo
    @cmd('redo')
    def redo(self, event=None):
        '''Redo the operation undone by the last undo.'''
        u = self; c = u.c
        w = c.frame.body.wrapper
        if not c.p:
            return
        # End editing *before* getting state.
        c.endEditing()
        if not u.canRedo():
            return
        if not u.getBead(u.bead + 1):
            return
        u.redoing = True
        u.groupCount = 0
        if u.redoHelper:
            u.redoHelper()
        else:
            g.trace('no redo helper for %s %s' % (u.kind, u.undoType))
        c.checkOutline()
        # Redraw and recolor.
        c.frame.body.updateEditors() # New in Leo 4.4.8.
        if 0: # Don't do this: it interferes with selection ranges.
            # This strange code forces a recomputation of the root position.
            c.selectPosition(c.p)
        else:
            c.setCurrentPosition(c.p)
        if u.newChanged is None: u.newChanged = True
        c.setChanged(u.newChanged)
        # Redrawing *must* be done here before setting u.undoing to False.
        i, j = w.getSelectionRange()
        ins = w.getInsertPoint()
        c.redraw()
        c.recolor()
        if u.inHead: # 2013/08/26.
            c.editHeadline()
            u.inHead = False
        else:
            c.bodyWantsFocus()
            w.setSelectionRange(i, j, insert=ins)
            w.seeInsertPoint()
        u.redoing = False
        u.bead += 1
        u.setUndoTypes()
    #@+node:ekr.20110519074734.6092: *3* u.redo helpers
    #@+node:ekr.20050424170219: *4* u.redoClearRecentFiles
    def redoClearRecentFiles(self):
        u = self; c = u.c
        rf = g.app.recentFilesManager
        rf.setRecentFiles(u.newRecentFiles[:])
        rf.createRecentFilesMenuItems(c)
    #@+node:ekr.20111005152227.15558: *4* u.redoCloneMarkedNodes
    def redoCloneMarkedNodes(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.cloneMarked()
        u.newP = c.p
        u.newChanged = c.isChanged()
    #@+node:ekr.20160502175557.1: *4* u.redoCopyMarkedNodes
    def redoCopyMarkedNodes(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.copyMarked()
        u.newP = c.p
        u.newChanged = c.isChanged()
    #@+node:ekr.20050412083057: *4* u.redoCloneNode
    def redoCloneNode(self):
        u = self; c = u.c; cc = c.chapterController
        if cc: cc.selectChapterByName('main')
        if u.newBack:
            u.newP._linkAfter(u.newBack)
        elif u.newParent:
            u.newP._linkAsNthChild(u.newParent, 0)
        else:
            oldRoot = c.rootPosition()
            u.newP._linkAsRoot(oldRoot)
        for v in u.dirtyVnodeList:
            v.setDirty()
        c.selectPosition(u.newP)
    #@+node:ekr.20111005152227.15559: *4* u.redoDeleteMarkedNodes
    def redoDeleteMarkedNodes(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.deleteMarked()
        c.selectPosition(u.newP)
        u.newChanged = c.isChanged()
    #@+node:EKR.20040526072519.2: *4* u.redoDeleteNode
    def redoDeleteNode(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.deleteOutline()
        c.selectPosition(u.newP)
    #@+node:ekr.20080425060424.9: *4* u.redoDemote
    def redoDemote(self):
        u = self; c = u.c
        parent_v = u.p._parentVnode()
        n = u.p.childIndex()
        # Move the demoted nodes from the old parent to the new parent.
        parent_v.children = parent_v.children[: n + 1]
        u.p.v.children.extend(u.followingSibs)
        # Adjust the parent links of the moved nodes.
        # There is no need to adjust descendant links.
        for v in u.followingSibs:
            v.parents.remove(parent_v)
            v.parents.append(u.p.v)
        c.setCurrentPosition(u.p)
    #@+node:ekr.20050318085432.6: *4* u.redoGroup
    def redoGroup(self):
        '''Process beads until the matching 'afterGroup' bead is seen.'''
        u = self
        # Remember these values.
        c = u.c
        dirtyVnodeList = u.dirtyVnodeList or []
        newSel = u.newSel
        p = u.p.copy()
        u.groupCount += 1
        bunch = u.beads[u.bead]; count = 0
        if not hasattr(bunch, 'items'):
            g.trace('oops: expecting bunch.items.  bunch.kind = %s' % bunch.kind)
            g.trace(bunch)
        else:
            for z in bunch.items:
                self.setIvarsFromBunch(z)
                if z.redoHelper:
                    z.redoHelper(); count += 1
                else:
                    g.trace('oops: no redo helper for %s %s' % (u.undoType, p.h))
        u.groupCount -= 1
        u.updateMarks('new') # Bug fix: Leo 4.4.6.
        for v in dirtyVnodeList:
            v.setDirty()
        if not g.unitTesting and u.verboseUndoGroup:
            g.es("redo", count, "instances")
        c.selectPosition(p)
        if newSel:
            i, j = newSel
            c.frame.body.wrapper.setSelectionRange(i, j)
    #@+node:ekr.20050412085138.1: *4* u.redoHoistNode & redoDehoistNode
    def redoHoistNode(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.hoist()

    def redoDehoistNode(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.dehoist()
    #@+node:ekr.20050412084532: *4* u.redoInsertNode
    def redoInsertNode(self):
        u = self; c = u.c; cc = c.chapterController
        if cc:
            cc.selectChapterByName('main')
        if u.newBack:
            u.newP._linkAfter(u.newBack)
        elif u.newParent:
            u.newP._linkAsNthChild(u.newParent, 0)
        else:
            oldRoot = c.rootPosition()
            u.newP._linkAsRoot(oldRoot)
        if u.pasteAsClone:
            for bunch in u.afterTree:
                v = bunch.v
                if u.newP.v == v:
                    c.setBodyString(u.newP, bunch.body)
                    c.setHeadString(u.newP, bunch.head)
                else:
                    v.setBodyString(bunch.body)
                    v.setHeadString(bunch.head)
        c.selectPosition(u.newP)
    #@+node:ekr.20050526125801: *4* u.redoMark
    def redoMark(self):
        u = self; c = u.c
        u.updateMarks('new')
        if u.groupCount == 0:
            for v in u.dirtyVnodeList:
                v.setDirty()
            c.selectPosition(u.p)
    #@+node:ekr.20050411111847: *4* u.redoMove
    def redoMove(self):
        u = self; c = u.c; cc = c.chapterController
        v = u.p.v
        assert(u.oldParent_v)
        assert(u.newParent_v)
        assert(v)
        if cc: cc.selectChapterByName('main')
        # Adjust the children arrays.
        assert u.oldParent_v.children[u.oldN] == v
        del u.oldParent_v.children[u.oldN]
        parent_v = u.newParent_v
        parent_v.children.insert(u.newN, v)
        v.parents.append(u.newParent_v)
        v.parents.remove(u.oldParent_v)
        u.updateMarks('new')
        for v in u.dirtyVnodeList:
            v.setDirty()
        c.selectPosition(u.newP)
    #@+node:ekr.20050318085432.7: *4* u.redoNodeContents
    def redoNodeContents(self):
        u = self; c = u.c; w = c.frame.body.wrapper
        # Restore the body.
        u.p.setBodyString(u.newBody)
        w.setAllText(u.newBody)
        c.frame.body.recolor(u.p)
        # Restore the headline.
        u.p.initHeadString(u.newHead)
        # This is required so.  Otherwise redraw will revert the change!
        c.frame.tree.setHeadline(u.p, u.newHead) # New in 4.4b2.
        if u.groupCount == 0 and u.newSel:
            i, j = u.newSel
            w.setSelectionRange(i, j)
        if u.groupCount == 0 and u.newYScroll is not None:
            w.setYScrollPosition(u.newYScroll)
        u.updateMarks('new')
        for v in u.dirtyVnodeList:
            v.setDirty()
    #@+node:ekr.20080425060424.13: *4* u.redoPromote
    def redoPromote(self):
        u = self; c = u.c
        parent_v = u.p._parentVnode()
        # Add the children to parent_v's children.
        n = u.p.childIndex() + 1
        old_children = parent_v.children[:]
        parent_v.children = old_children[: n]
            # Add children up to the promoted nodes.
        parent_v.children.extend(u.children)
            # Add the promoted nodes.
        parent_v.children.extend(old_children[n:])
            # Add the children up to the promoted nodes.
        # Remove the old children.
        u.p.v.children = []
        # Adjust the parent links in the moved children.
        # There is no need to adjust descendant links.
        for child in u.children:
            child.parents.remove(u.p.v)
            child.parents.append(parent_v)
        c.setCurrentPosition(u.p)
    #@+node:ekr.20080425060424.4: *4* u.redoSort
    def redoSort(self):
        u = self; c = u.c
        parent_v = u.p._parentVnode()
        parent_v.children = u.newChildren
        p = c.setPositionAfterSort(u.sortChildren)
        c.setCurrentPosition(p)
    #@+node:ekr.20050318085432.8: *4* u.redoTree
    def redoTree(self):
        '''Redo replacement of an entire tree.'''
        u = self; c = u.c
        u.p = self.undoRedoTree(u.p, u.oldTree, u.newTree)
        c.selectPosition(u.p) # Does full recolor.
        if u.newSel:
            i, j = u.newSel
            c.frame.body.wrapper.setSelectionRange(i, j)
    #@+node:EKR.20040526075238.5: *4* u.redoTyping
    def redoTyping(self):
        u = self; c = u.c; current = c.p
        w = c.frame.body.wrapper
        # selectPosition causes recoloring, so avoid if possible.
        if current != u.p:
            c.selectPosition(u.p)
        self.undoRedoText(
            u.p, u.leading, u.trailing,
            u.newMiddleLines, u.oldMiddleLines,
            u.newNewlines, u.oldNewlines,
            tag="redo", undoType=u.undoType)
        u.updateMarks('new')
        for v in u.dirtyVnodeList:
            v.setDirty()
        if u.newSel:
            c.bodyWantsFocus()
            i, j = u.newSel
            w.setSelectionRange(i, j, insert=j)
        if u.yview:
            c.bodyWantsFocus()
            w.setYScrollPosition(u.yview)
    #@+node:ekr.20031218072017.2039: *3* u.undo
    @cmd('undo')
    def undo(self, event=None):
        """Undo the operation described by the undo parameters."""
        u = self; c = u.c
        w = c.frame.body.wrapper
        if not c.p:
            g.trace('no current position')
            return
        # End editing *before* getting state.
        c.endEditing()
        if u.per_node_undo: # 2011/05/19
            u.setIvarsFromVnode(c.p)
        if not u.canUndo():
            return
        if not u.getBead(u.bead):
            return
        u.undoing = True
        u.groupCount = 0
        if u.undoHelper:
            u.undoHelper()
        else:
            g.trace('no undo helper for %s %s' % (u.kind, u.undoType))
        c.checkOutline()
        # Redraw and recolor.
        c.frame.body.updateEditors() # New in Leo 4.4.8.
        if 0: # Don't do this: it interferes with selection ranges.
            # This strange code forces a recomputation of the root position.
            c.selectPosition(c.p)
        else:
            c.setCurrentPosition(c.p)
        if u.oldChanged is None: u.oldChanged = True
        c.setChanged(u.oldChanged)
        # Redrawing *must* be done here before setting u.undoing to False.
        i, j = w.getSelectionRange()
        ins = w.getInsertPoint()
        c.redraw()
        c.recolor()
        if u.inHead:
            c.editHeadline()
            u.inHead = False
        else:
            c.bodyWantsFocus()
            w.setSelectionRange(i, j, insert=ins)
            w.seeInsertPoint()
        u.undoing = False
        u.bead -= 1
        u.setUndoTypes()
    #@+node:ekr.20110519074734.6093: *3* u.undo helpers
    #@+node:ekr.20050424170219.1: *4* u.undoClearRecentFiles
    def undoClearRecentFiles(self):
        u = self; c = u.c
        rf = g.app.recentFilesManager
        rf.setRecentFiles(u.oldRecentFiles[:])
        rf.createRecentFilesMenuItems(c)
    #@+node:ekr.20111005152227.15560: *4* u.undoCloneMarkedNodes
    def undoCloneMarkedNodes(self):
        u = self
        next = u.p.next()
        assert next.h == 'Clones of marked nodes', (u.p, next.h)
        next.doDelete()
        u.p.setAllAncestorAtFileNodesDirty()
        u.c.selectPosition(u.p)
    #@+node:ekr.20160502175653.1: *4* u.undoCopyMarkedNodes
    def undoCopyMarkedNodes(self):
        u = self
        next = u.p.next()
        assert next.h == 'Copies of marked nodes', (u.p.h, next.h)
        next.doDelete()
        u.p.setAllAncestorAtFileNodesDirty()
        u.c.selectPosition(u.p)
    #@+node:ekr.20050412083057.1: *4* u.undoCloneNode
    def undoCloneNode(self):
        u = self; c = u.c; cc = c.chapterController
        if cc: cc.selectChapterByName('main')
        c.selectPosition(u.newP)
        c.deleteOutline()
        for v in u.dirtyVnodeList:
            v.setDirty() # Bug fix: Leo 4.4.6
        c.selectPosition(u.p)
    #@+node:ekr.20111005152227.15557: *4* u.undoDeleteMarkedNodes
    def undoDeleteMarkedNodes(self):
        u = self; c = u.c
        # Undo the deletes in reverse order
        aList = u.deleteMarkedNodesData[:]
        aList.reverse()
        for p in aList:
            if p.stack:
                parent_v, junk = p.stack[-1]
            else:
                parent_v = c.hiddenRootNode
            p.v._addLink(p._childIndex, parent_v)
        u.p.setAllAncestorAtFileNodesDirty()
        c.selectPosition(u.p)
    #@+node:ekr.20050412084055: *4* u.undoDeleteNode
    def undoDeleteNode(self):
        u = self; c = u.c
        if u.oldBack:
            u.p._linkAfter(u.oldBack)
        elif u.oldParent:
            u.p._linkAsNthChild(u.oldParent, 0)
        else:
            oldRoot = c.rootPosition()
            u.p._linkAsRoot(oldRoot)
        u.p.setAllAncestorAtFileNodesDirty()
        c.selectPosition(u.p)
    #@+node:ekr.20080425060424.10: *4* u.undoDemote
    def undoDemote(self):
        u = self; c = u.c
        parent_v = u.p._parentVnode()
        n = len(u.followingSibs)
        # Remove the demoted nodes from p's children.
        u.p.v.children = u.p.v.children[: -n]
        # Add the demoted nodes to the parent's children.
        parent_v.children.extend(u.followingSibs)
        # Adjust the parent links.
        # There is no need to adjust descendant links.
        for sib in u.followingSibs:
            sib.parents.remove(u.p.v)
            sib.parents.append(parent_v)
        c.setCurrentPosition(u.p)
    #@+node:ekr.20050318085713: *4* u.undoGroup
    def undoGroup(self):
        '''Process beads until the matching 'beforeGroup' bead is seen.'''
        u = self
        # Remember these values.
        c = u.c
        dirtyVnodeList = u.dirtyVnodeList or []
        oldSel = u.oldSel
        p = u.p.copy()
        u.groupCount += 1
        bunch = u.beads[u.bead]; count = 0
        if not hasattr(bunch, 'items'):
            g.trace('oops: expecting bunch.items.  bunch.kind = %s' % bunch.kind)
            g.trace(bunch)
        else:
            # Important bug fix: 9/8/06: reverse the items first.
            reversedItems = bunch.items[:]
            reversedItems.reverse()
            for z in reversedItems:
                self.setIvarsFromBunch(z)
                if z.undoHelper:
                    z.undoHelper(); count += 1
                else:
                    g.trace('oops: no undo helper for %s %s' % (u.undoType, p.v))
        u.groupCount -= 1
        u.updateMarks('old') # Bug fix: Leo 4.4.6.
        for v in dirtyVnodeList:
            v.setDirty() # Bug fix: Leo 4.4.6.
        if not g.unitTesting and u.verboseUndoGroup:
            g.es("undo", count, "instances")
        c.selectPosition(p)
        if oldSel:
            i, j = oldSel
            c.frame.body.wrapper.setSelectionRange(i, j)
    #@+node:ekr.20050412083244: *4* u.undoHoistNode & undoDehoistNode
    def undoHoistNode(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.dehoist()

    def undoDehoistNode(self):
        u = self; c = u.c
        c.selectPosition(u.p)
        c.hoist()
    #@+node:ekr.20050412085112: *4* u.undoInsertNode
    def undoInsertNode(self):
        u = self; c = u.c; cc = c.chapterController
        if cc: cc.selectChapterByName('main')
        c.selectPosition(u.newP)
        c.deleteOutline()
            # Bug fix: 2016/03/30.
            # This always selects the proper new position.
            # c.selectPosition(u.p)
        if u.pasteAsClone:
            for bunch in u.beforeTree:
                v = bunch.v
                if u.p.v == v:
                    c.setBodyString(u.p, bunch.body)
                    c.setHeadString(u.p, bunch.head)
                else:
                    v.setBodyString(bunch.body)
                    v.setHeadString(bunch.head)
    #@+node:ekr.20050526124906: *4* u.undoMark
    def undoMark(self):
        u = self; c = u.c
        u.updateMarks('old')
        if u.groupCount == 0:
            for v in u.dirtyVnodeList:
                v.setDirty() # Bug fix: Leo 4.4.6.
            c.selectPosition(u.p)
    #@+node:ekr.20050411112033: *4* u.undoMove
    def undoMove(self):

        u = self; c = u.c; cc = c.chapterController
        if cc: cc.selectChapterByName('main')
        v = u.p.v
        assert(u.oldParent_v)
        assert(u.newParent_v)
        assert(v)
        # Adjust the children arrays.
        assert u.newParent_v.children[u.newN] == v
        del u.newParent_v.children[u.newN]
        u.oldParent_v.children.insert(u.oldN, v)
        # Recompute the parent links.
        v.parents.append(u.oldParent_v)
        v.parents.remove(u.newParent_v)
        u.updateMarks('old')
        for v in u.dirtyVnodeList:
            v.setDirty()
        c.selectPosition(u.p)
    #@+node:ekr.20050318085713.1: *4* u.undoNodeContents
    def undoNodeContents(self):
        '''Undo all changes to the contents of a node,
        including headline and body text, and marked bits.
        '''
        u = self; c = u.c
        w = c.frame.body.wrapper
        u.p.b = u.oldBody
        w.setAllText(u.oldBody)
        c.frame.body.recolor(u.p)
        u.p.h = u.oldHead
        # This is required.  Otherwise c.redraw will revert the change!
        c.frame.tree.setHeadline(u.p, u.oldHead)
        if u.groupCount == 0 and u.oldSel:
            i, j = u.oldSel
            w.setSelectionRange(i, j)
        if u.groupCount == 0 and u.oldYScroll is not None:
            w.setYScrollPosition(u.oldYScroll)
        u.updateMarks('old')
        for v in u.dirtyVnodeList:
            v.setDirty() # Bug fix: Leo 4.4.6.
    #@+node:ekr.20080425060424.14: *4* u.undoPromote
    def undoPromote(self):
        u = self; c = u.c
        parent_v = u.p._parentVnode() # The parent of the all the *promoted* nodes.
        # Remove the promoted nodes from parent_v's children.
        n = u.p.childIndex() + 1
        # Adjust the old parents children
        old_children = parent_v.children
        parent_v.children = old_children[: n]
            # Add the nodes before the promoted nodes.
        parent_v.children.extend(old_children[n + len(u.children):])
            # Add the nodes after the promoted nodes.
        # Add the demoted nodes to v's children.
        u.p.v.children = u.children[:]
        # Adjust the parent links.
        # There is no need to adjust descendant links.
        for child in u.children:
            child.parents.remove(parent_v)
            child.parents.append(u.p.v)
        c.setCurrentPosition(u.p)
    #@+node:ekr.20031218072017.1493: *4* u.undoRedoText
    def undoRedoText(self, p,
        leading, trailing, # Number of matching leading & trailing lines.
        oldMidLines, newMidLines, # Lists of unmatched lines.
        oldNewlines, newNewlines, # Number of trailing newlines.
        tag="undo", # "undo" or "redo"
        undoType=None
    ):
        '''Handle text undo and redo: converts _new_ text into _old_ text.'''
        # newNewlines is unused, but it has symmetry.
        u = self; c = u.c; w = c.frame.body.wrapper
        #@+<< Compute the result using p's body text >>
        #@+node:ekr.20061106105812.1: *5* << Compute the result using p's body text >>
        # Recreate the text using the present body text.
        body = p.b
        body = g.checkUnicode(body)
        body_lines = body.split('\n')
        s = []
        if leading > 0:
            s.extend(body_lines[: leading])
        if oldMidLines:
            s.extend(oldMidLines)
        if trailing > 0:
            s.extend(body_lines[-trailing:])
        s = '\n'.join(s)
        # Remove trailing newlines in s.
        while s and s[-1] == '\n':
            s = s[: -1]
        # Add oldNewlines newlines.
        if oldNewlines > 0:
            s = s + '\n' * oldNewlines
        result = s
        if u.debug_print:
            g.pr("body:  ", body)
            g.pr("result:", result)
        #@-<< Compute the result using p's body text >>
        p.setBodyString(result)
        w.setAllText(result)
        sel = u.oldSel if tag == 'undo' else u.newSel
        if sel:
            i, j = sel
            w.setSelectionRange(i, j, insert=j)
        c.frame.body.recolor(p)
        w.seeInsertPoint() # 2009/12/21
    #@+node:ekr.20050408100042: *4* u.undoRedoTree
    def undoRedoTree(self, p, new_data, old_data):
        '''Replace p and its subtree using old_data during undo.'''
        # Same as undoReplace except uses g.Bunch.
        u = self; c = u.c
        if new_data is None:
            # This is the first time we have undone the operation.
            # Put the new data in the bead.
            bunch = u.beads[u.bead]
            bunch.newTree = u.saveTree(p.copy())
            u.beads[u.bead] = bunch
        # Replace data in tree with old data.
        u.restoreTree(old_data)
        c.setBodyString(p, p.b)
        return p # Nothing really changes.
    #@+node:ekr.20080425060424.5: *4* u.undoSort
    def undoSort(self):
        u = self; c = u.c
        parent_v = u.p._parentVnode()
        parent_v.children = u.oldChildren
        p = c.setPositionAfterSort(u.sortChildren)
        c.setCurrentPosition(p)
    #@+node:ekr.20050318085713.2: *4* u.undoTree
    def undoTree(self):
        '''Redo replacement of an entire tree.'''
        u = self; c = u.c
        u.p = self.undoRedoTree(u.p, u.newTree, u.oldTree)
        c.selectPosition(u.p) # Does full recolor.
        if u.oldSel:
            i, j = u.oldSel
            c.frame.body.wrapper.setSelectionRange(i, j)
    #@+node:EKR.20040526090701.4: *4* u.undoTyping
    def undoTyping(self):
        u = self; c = u.c; current = c.p
        w = c.frame.body.wrapper
        # selectPosition causes recoloring, so don't do this unless needed.
        if current != u.p:
            c.selectPosition(u.p)
        self.undoRedoText(
            u.p, u.leading, u.trailing,
            u.oldMiddleLines, u.newMiddleLines,
            u.oldNewlines, u.newNewlines,
            tag="undo", undoType=u.undoType)
        u.updateMarks('old')
        for v in u.dirtyVnodeList:
            v.setDirty() # Bug fix: Leo 4.4.6.
        if u.oldSel:
            c.bodyWantsFocus()
            i, j = u.oldSel
            w.setSelectionRange(i, j, insert=j)
        if u.yview:
            c.bodyWantsFocus()
            w.setYScrollPosition(u.yview)
    #@-others
#@-others
#@@language python
#@@tabwidth -4
#@@pagewidth 70
#@-leo
