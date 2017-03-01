describe 'Problem', ->
  problem_content_default = readFixtures('problem_content.html')

  beforeEach ->
    # Stub MathJax
    window.MathJax =
      Hub: jasmine.createSpyObj('MathJax.Hub', ['getAllJax', 'Queue'])
      Callback: jasmine.createSpyObj('MathJax.Callback', ['After'])
    @stubbedJax = root: jasmine.createSpyObj('jax.root', ['toMathML'])
    MathJax.Hub.getAllJax.and.returnValue [@stubbedJax]
    window.update_schematics = ->
    spyOn SR, 'readText'
    spyOn SR, 'readTexts'

    # Load this function from spec/helper.coffee
    # Note that if your test fails with a message like:
    # 'External request attempted for blah, which is not defined.'
    # this msg is coming from the stubRequests function else clause.
    jasmine.stubRequests()

    loadFixtures 'problem.html'

    spyOn Logger, 'log'
    spyOn($.fn, 'load').and.callFake (url, callback) ->
      $(@).html readFixtures('problem_content.html')
      callback()

  describe 'constructor', ->

    it 'set the element from html', ->
      @problem999 = new Problem ("
        <section class='xblock xblock-student_view xmodule_display xmodule_CapaModule' data-type='Problem'>
          <section id='problem_999'
                   class='problems-wrapper'
                   data-problem-id='i4x://edX/999/problem/Quiz'
                   data-url='/problem/quiz/'>
          </section>
        </section>
        ")
      expect(@problem999.element_id).toBe 'problem_999'

    it 'set the element from loadFixtures', ->
      @problem1 = new Problem($('.xblock-student_view'))
      expect(@problem1.element_id).toBe 'problem_1'

  describe 'bind', ->
    beforeEach ->
      spyOn window, 'update_schematics'
      MathJax.Hub.getAllJax.and.returnValue [@stubbedJax]
      @problem = new Problem($('.xblock-student_view'))

    it 'set mathjax typeset', ->
      expect(MathJax.Hub.Queue).toHaveBeenCalled()

    it 'update schematics', ->
      expect(window.update_schematics).toHaveBeenCalled()

    it 'bind answer refresh on button click', ->
      expect($('div.action button')).toHandleWith 'click', @problem.refreshAnswers

    it 'bind the submit button', ->
      expect($('.action .submit')).toHandleWith 'click', @problem.submit_fd

    it 'bind the reset button', ->
      expect($('div.action button.reset')).toHandleWith 'click', @problem.reset

    it 'bind the show button', ->
      expect($('.action .show')).toHandleWith 'click', @problem.show

    it 'bind the save button', ->
      expect($('div.action button.save')).toHandleWith 'click', @problem.save

    it 'bind the math input', ->
      expect($('input.math')).toHandleWith 'keyup', @problem.refreshMath

  describe 'bind_with_custom_input_id', ->
    beforeEach ->
      spyOn window, 'update_schematics'
      MathJax.Hub.getAllJax.and.returnValue [@stubbedJax]
      @problem = new Problem($('.xblock-student_view'))
      $(@).html readFixtures('problem_content_1240.html')

    it 'bind the submit button', ->
      expect($('.action .submit')).toHandleWith 'click', @problem.submit_fd

    it 'bind the show button', ->
      expect($('div.action button.show')).toHandleWith 'click', @problem.show


  describe 'renderProgressState', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))

    testProgessData = (problem, score, total_possible, attempts, graded, expected_progress_after_render) ->
      problem.el.data('problem-score', score);
      problem.el.data('problem-total-possible', total_possible);
      problem.el.data('attempts-used', attempts);
      problem.el.data('graded', graded)
      expect(problem.$('.problem-progress').html()).toEqual ""
      problem.renderProgressState()
      expect(problem.$('.problem-progress').html()).toEqual expected_progress_after_render

    describe 'with a status of "none"', ->
      it 'reports the number of points possible and graded', ->
        testProgessData(@problem, 0, 1, 0, "True", "1 point possible (graded)")

      it 'displays the number of points possible when rendering happens with the content', ->
        testProgessData(@problem, 0, 2, 0, "True", "2 points possible (graded)")

      it 'reports the number of points possible and ungraded', ->
        testProgessData(@problem, 0, 1, 0, "False", "1 point possible (ungraded)")

      it 'displays ungraded if number of points possible is 0', ->
        testProgessData(@problem, 0, 0, 0, "False", "0 points possible (ungraded)")

      it 'displays ungraded if number of points possible is 0, even if graded value is True', ->
        testProgessData(@problem, 0, 0, 0, "True", "0 points possible (ungraded)")

      it 'reports the correct score with status none and >0 attempts', ->
        testProgessData(@problem, 0, 1, 1, "True", "0/1 point (graded)")

      it 'reports the correct score with >1 weight, status none, and >0 attempts', ->
        testProgessData(@problem, 0, 2, 2, "True", "0/2 points (graded)")

    describe 'with any other valid status', ->

      it 'reports the current score', ->
        testProgessData(@problem, 1, 1, 1, "True", "1/1 point (graded)")

      it 'shows current score when rendering happens with the content', ->
        testProgessData(@problem, 2, 2, 1, "True", "2/2 points (graded)")

      it 'reports the current score even if problem is ungraded', ->
        testProgessData(@problem, 1, 1, 1, "False", "1/1 point (ungraded)")

    describe 'with valid status and string containing an integer like "0" for detail', ->
      # These tests are to address a failure specific to Chrome 51 and 52 +
      it 'shows 0 points possible for the detail', ->
        testProgessData(@problem, 0, 0, 1, "False", "0 points possible (ungraded)")

  describe 'render', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @bind = @problem.bind
      spyOn @problem, 'bind'

    describe 'with content given', ->
      beforeEach ->
        @problem.render 'Hello World'

      it 'render the content', ->
        expect(@problem.el.html()).toEqual 'Hello World'

      it 're-bind the content', ->
        expect(@problem.bind).toHaveBeenCalled()

    describe 'with no content given', ->
      beforeEach ->
        spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
          callback html: "Hello World"
        @problem.render()

      it 'load the content via ajax', ->
        expect(@problem.el.html()).toEqual 'Hello World'

      it 're-bind the content', ->
        expect(@problem.bind).toHaveBeenCalled()

  describe 'submit_fd', ->
    beforeEach ->
      # Insert an input of type file outside of the problem.
      $('.xblock-student_view').after('<input type="file" />')
      @problem = new Problem($('.xblock-student_view'))
      spyOn(@problem, 'submit')

    it 'submit method is called if input of type file is not in problem', ->
      @problem.submit_fd()
      expect(@problem.submit).toHaveBeenCalled()

  describe 'submit', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @problem.answers = 'foo=1&bar=2'

    it 'log the problem_check event', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        promise =
          always: (callable) -> callable()
          done: (callable) -> callable()
      @problem.submit()
      expect(Logger.log).toHaveBeenCalledWith 'problem_check', 'foo=1&bar=2'

    it 'log the problem_graded event, after the problem is done grading.', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        response =
          success: 'correct'
          contents: 'mock grader response'
        callback(response)
        promise =
          always: (callable) -> callable()
          done: (callable) -> callable()
      @problem.submit()
      expect(Logger.log).toHaveBeenCalledWith 'problem_graded', ['foo=1&bar=2', 'mock grader response'], @problem.id

    it 'submit the answer for submit', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        promise =
          always: (callable) -> callable()
          done: (callable) -> callable()
      @problem.submit()
      expect($.postWithPrefix).toHaveBeenCalledWith '/problem/Problem1/problem_check',
          'foo=1&bar=2', jasmine.any(Function)

    describe 'when the response is correct', ->
      it 'call render with returned content', ->
        contents = '<div class="wrapper-problem-response" aria-label="Question 1"><p>Correct<span class="status">excellent</span></p></div>' +
                   '<div class="wrapper-problem-response" aria-label="Question 2"><p>Yep<span class="status">correct</span></p></div>'
        spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
          callback(success: 'correct', contents: contents)
          promise =
            always: (callable) -> callable()
            done: (callable) -> callable()
        @problem.submit()
        expect(@problem.el).toHaveHtml contents
        expect(window.SR.readTexts).toHaveBeenCalledWith ['Question 1: excellent', 'Question 2: correct']

    describe 'when the response is incorrect', ->
      it 'call render with returned content', ->
        contents = '<p>Incorrect<span class="status">no, try again</span></p>'
        spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
          callback(success: 'incorrect', contents: contents)
          promise =
            always: (callable) -> callable()
            done: (callable) -> callable()
        @problem.submit()
        expect(@problem.el).toHaveHtml contents
        expect(window.SR.readTexts).toHaveBeenCalledWith ['no, try again']

    it 'tests if the submit button is disabled while submitting and the text changes on the button', ->
      self = this
      curr_html = @problem.el.html()
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        # At this point enableButtons should have been called, making the submit button disabled with text 'submitting'
        expect(self.problem.submitButton).toHaveAttr('disabled');
        expect(self.problem.submitButtonLabel.text()).toBe('Submitting');
        callback
          success: 'incorrect' # does not matter if correct or incorrect here
          contents: curr_html
        promise =
          always: (callable) -> callable()
          done: (callable) -> callable()
      # Make sure the submit button is enabled before submitting
      $('#input_example_1').val('test').trigger('input')
      expect(@problem.submitButton).not.toHaveAttr('disabled')
      @problem.submit()
      # After submit, the button should not be disabled and should have text as 'Submit'
      expect(@problem.submitButtonLabel.text()).toBe('Submit')
      expect(@problem.submitButton).not.toHaveAttr('disabled')

  describe 'submit button on problems', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @submitDisabled = (disabled) =>
        if disabled
          expect(@problem.submitButton).toHaveAttr('disabled')
        else
          expect(@problem.submitButton).not.toHaveAttr('disabled')

    describe 'some basic tests for submit button', ->
      it 'should become enabled after a value is entered into the text box', ->
        $('#input_example_1').val('test').trigger('input')
        @submitDisabled false
        $('#input_example_1').val('').trigger('input')
        @submitDisabled true

    describe 'some advanced tests for submit button', ->
      it 'should become enabled after a checkbox is checked', ->
        html = '''
        <div class="choicegroup">
        <label for="input_1_1_1"><input type="checkbox" name="input_1_1" id="input_1_1_1" value="1"> One</label>
        <label for="input_1_1_2"><input type="checkbox" name="input_1_1" id="input_1_1_2" value="2"> Two</label>
        <label for="input_1_1_3"><input type="checkbox" name="input_1_1" id="input_1_1_3" value="3"> Three</label>
        </div>
        '''
        $('#input_example_1').replaceWith(html)
        @problem.submitAnswersAndSubmitButton true
        @submitDisabled true
        $('#input_1_1_1').click()
        @submitDisabled false
        $('#input_1_1_1').click()
        @submitDisabled true

      it 'should become enabled after a radiobutton is checked', ->
        html = '''
        <div class="choicegroup">
        <label for="input_1_1_1"><input type="radio" name="input_1_1" id="input_1_1_1" value="1"> One</label>
        <label for="input_1_1_2"><input type="radio" name="input_1_1" id="input_1_1_2" value="2"> Two</label>
        <label for="input_1_1_3"><input type="radio" name="input_1_1" id="input_1_1_3" value="3"> Three</label>
        </div>
        '''
        $('#input_example_1').replaceWith(html)
        @problem.submitAnswersAndSubmitButton true
        @submitDisabled true
        $('#input_1_1_1').attr('checked', true).trigger('click')
        @submitDisabled false
        $('#input_1_1_1').attr('checked', false).trigger('click')
        @submitDisabled true

      it 'should become enabled after a value is selected in a selector', ->
        html = '''
        <div id="problem_sel">
        <select>
        <option value="val0">Select an option</option>
        <option value="val1">1</option>
        <option value="val2">2</option>
        </select>
        </div>
        '''
        $('#input_example_1').replaceWith(html)
        @problem.submitAnswersAndSubmitButton true
        @submitDisabled true
        $("#problem_sel select").val("val2").trigger('change')
        @submitDisabled false
        $("#problem_sel select").val("val0").trigger('change')
        @submitDisabled true

      it 'should become enabled after a radiobutton is checked and a value is entered into the text box', ->
        html = '''
        <div class="choicegroup">
        <label for="input_1_1_1"><input type="radio" name="input_1_1" id="input_1_1_1" value="1"> One</label>
        <label for="input_1_1_2"><input type="radio" name="input_1_1" id="input_1_1_2" value="2"> Two</label>
        <label for="input_1_1_3"><input type="radio" name="input_1_1" id="input_1_1_3" value="3"> Three</label>
        </div>
        '''
        $(html).insertAfter('#input_example_1')
        @problem.submitAnswersAndSubmitButton true
        @submitDisabled true
        $('#input_1_1_1').attr('checked', true).trigger('click')
        @submitDisabled true
        $('#input_example_1').val('111').trigger('input')
        @submitDisabled false
        $('#input_1_1_1').attr('checked', false).trigger('click')
        @submitDisabled true

      it 'should become enabled if there are only hidden input fields', ->
        html = '''
        <input type="text" name="test" id="test" aria-describedby="answer_test" value="" style="display:none;">
        '''
        $('#input_example_1').replaceWith(html)
        @problem.submitAnswersAndSubmitButton true
        @submitDisabled false

  describe 'reset', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))

    it 'log the problem_reset event', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        promise =
          always: (callable) -> callable()
      @problem.answers = 'foo=1&bar=2'
      @problem.reset()
      expect(Logger.log).toHaveBeenCalledWith 'problem_reset', 'foo=1&bar=2'

    it 'POST to the problem reset page', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        promise =
          always: (callable) -> callable()
      @problem.reset()
      expect($.postWithPrefix).toHaveBeenCalledWith '/problem/Problem1/problem_reset',
          { id: 'i4x://edX/101/problem/Problem1' }, jasmine.any(Function)

    it 'render the returned content', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        callback html: "Reset", success: true
        promise =
            always: (callable) -> callable()
      @problem.reset()
      expect(@problem.el.html()).toEqual 'Reset'

    it 'sends a message to the window SR element', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        callback html: "Reset", success: true
        promise =
          always: (callable) -> callable()
       @problem.reset()
       expect(window.SR.readText).toHaveBeenCalledWith 'This problem has been reset.'

    it 'shows a notification on error', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        callback msg: "Error on reset.", success: false
        promise =
          always: (callable) -> callable()
      @problem.reset()
      expect($('.notification-gentle-alert .notification-message').text()).toEqual("Error on reset.")

    it 'tests that reset does not enable submit or modify the text while resetting', ->
      self = this
      curr_html = @problem.el.html()
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        # enableButtons should have been called at this point to set them to all disabled
        expect(self.problem.submitButton).toHaveAttr('disabled')
        expect(self.problem.submitButtonLabel.text()).toBe('Submit')
        callback(success: 'correct', html: curr_html)
        promise =
          always: (callable) -> callable()
      # Submit should be disabled
      expect(@problem.submitButton).toHaveAttr('disabled')
      @problem.reset()
      # Submit should remain disabled
      expect(self.problem.submitButton).toHaveAttr('disabled')
      expect(self.problem.submitButtonLabel.text()).toBe('Submit')

  describe 'show', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @problem.el.prepend '<div id="answer_1_1" /><div id="answer_1_2" />'

    describe 'when the answer has not yet shown', ->
      beforeEach ->
        expect(@problem.el.find('.show').attr('disabled')).not.toEqual('disabled')

      it 'log the problem_show event', ->
        @problem.show()
        expect(Logger.log).toHaveBeenCalledWith 'problem_show',
            problem: 'i4x://edX/101/problem/Problem1'

      it 'fetch the answers', ->
        spyOn $, 'postWithPrefix'
        @problem.show()
        expect($.postWithPrefix).toHaveBeenCalledWith '/problem/Problem1/problem_show',
            jasmine.any(Function)

      it 'show the answers', ->
        spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
          callback answers: '1_1': 'One', '1_2': 'Two'
        @problem.show()
        expect($('#answer_1_1')).toHaveHtml 'One'
        expect($('#answer_1_2')).toHaveHtml 'Two'

      it 'sends a message to the window SR element', ->
        spyOn($, 'postWithPrefix').and.callFake (url, callback) -> callback(answers: {})
        @problem.show()
        expect(window.SR.readText).toHaveBeenCalledWith 'Answers to this problem are now shown. Navigate through the problem to review it with answers inline.'

      it 'disables the show answer button', ->
        spyOn($, 'postWithPrefix').and.callFake (url, callback) -> callback(answers: {})
        @problem.show()
        expect(@problem.el.find('.show').attr('disabled')).toEqual('disabled')

      it 'sends a SR message when answer is present', ->

        spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
          callback answers:
            '1_1': 'answers'
        @problem.show()

        expect(window.SR.readText).toHaveBeenCalledWith 'Answers to this problem are now shown. Navigate through the problem to review it with answers inline.'

      describe 'radio text question', ->
        radio_text_xml='''
<section class="problem">
  <div><p></p><span><section id="choicetextinput_1_2_1" class="choicetextinput">

<form class="choicetextgroup capa_inputtype" id="inputtype_1_2_1">
  <div class="indicator-container">
    <span class="unanswered" style="display:inline-block;" id="status_1_2_1"></span>
  </div>
  <fieldset>
    <section id="forinput1_2_1_choiceinput_0bc">
      <input class="ctinput" type="radio" name="choiceinput_1_2_1" id="1_2_1_choiceinput_0bc" value="choiceinput_0"">
      <input class="ctinput" type="text" name="choiceinput_0_textinput_0" id="1_2_1_choiceinput_0_textinput_0" value=" ">
      <p id="answer_1_2_1_choiceinput_0bc" class="answer"></p>
    </>
    <section id="forinput1_2_1_choiceinput_1bc">
      <input class="ctinput" type="radio" name="choiceinput_1_2_1" id="1_2_1_choiceinput_1bc" value="choiceinput_1" >
      <input class="ctinput" type="text" name="choiceinput_1_textinput_0" id="1_2_1_choiceinput_1_textinput_0" value=" " >
      <p id="answer_1_2_1_choiceinput_1bc" class="answer"></p>
    </section>
    <section id="forinput1_2_1_choiceinput_2bc">
      <input class="ctinput" type="radio" name="choiceinput_1_2_1" id="1_2_1_choiceinput_2bc" value="choiceinput_2" >
      <input class="ctinput" type="text" name="choiceinput_2_textinput_0" id="1_2_1_choiceinput_2_textinput_0" value=" " >
      <p id="answer_1_2_1_choiceinput_2bc" class="answer"></p>
    </section></fieldset><input class="choicetextvalue" type="hidden" name="input_1_2_1" id="input_1_2_1"></form>
</section></span></div>
</section>
'''
        beforeEach ->
          # Append a radiotextresponse problem to the problem, so we can check it's javascript functionality
          @problem.el.prepend(radio_text_xml)

        it 'sets the correct class on the section for the correct choice', ->
          spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
            callback answers: "1_2_1": ["1_2_1_choiceinput_0bc"], "1_2_1_choiceinput_0bc": "3"
          @problem.show()

          expect($('#forinput1_2_1_choiceinput_0bc').attr('class')).toEqual(
            'choicetextgroup_show_correct')
          expect($('#answer_1_2_1_choiceinput_0bc').text()).toEqual('3')
          expect($('#answer_1_2_1_choiceinput_1bc').text()).toEqual('')
          expect($('#answer_1_2_1_choiceinput_2bc').text()).toEqual('')

        it 'Should not disable input fields', ->
          spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
            callback answers: "1_2_1": ["1_2_1_choiceinput_0bc"], "1_2_1_choiceinput_0bc": "3"
          @problem.show()
          expect($('input#1_2_1_choiceinput_0bc').attr('disabled')).not.toEqual('disabled')
          expect($('input#1_2_1_choiceinput_1bc').attr('disabled')).not.toEqual('disabled')
          expect($('input#1_2_1_choiceinput_2bc').attr('disabled')).not.toEqual('disabled')
          expect($('input#1_2_1').attr('disabled')).not.toEqual('disabled')

      describe 'imageinput', ->
        imageinput_html = readFixtures('imageinput.underscore')

        DEFAULTS =
          id: '12345'
          width: '300'
          height: '400'

        beforeEach ->
          @problem = new Problem($('.xblock-student_view'))
          @problem.el.prepend _.template(imageinput_html)(DEFAULTS)

        assertAnswer = (problem, data) =>
          stubRequest(data)
          problem.show()

          $.each data['answers'], (id, answer) =>
            img = getImage(answer)
            el = $('#inputtype_' + id)
            expect(img).toImageDiffEqual(el.find('canvas')[0])

        stubRequest = (data) =>
          spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
            callback data

        getImage = (coords, c_width, c_height) =>
          types =
            rectangle: (coords) =>
              reg = /^\(([0-9]+),([0-9]+)\)-\(([0-9]+),([0-9]+)\)$/
              rects = coords.replace(/\s*/g, '').split(/;/)

              $.each rects, (index, rect) =>
                abs = Math.abs
                points = reg.exec(rect)
                if points
                  width = abs(points[3] - points[1])
                  height = abs(points[4] - points[2])

                  ctx.rect(points[1], points[2], width, height)

              ctx.stroke()
              ctx.fill()

            regions: (coords) =>
              parseCoords = (coords) =>
                reg = JSON.parse(coords)

                if typeof reg[0][0][0] == "undefined"
                  reg = [reg]

                return reg

              $.each parseCoords(coords), (index, region) =>
                ctx.beginPath()
                $.each region, (index, point) =>
                  if index is 0
                    ctx.moveTo(point[0], point[1])
                  else
                    ctx.lineTo(point[0], point[1]);

                ctx.closePath()
                ctx.stroke()
                ctx.fill()

          canvas = document.createElement('canvas')
          canvas.width = c_width or 100
          canvas.height = c_height or 100

          if canvas.getContext
            ctx = canvas.getContext('2d')
          else
            return console.log 'Canvas is not supported.'

          ctx.fillStyle = 'rgba(255,255,255,.3)';
          ctx.strokeStyle = "#FF0000";
          ctx.lineWidth = "2";

          $.each coords, (key, value) =>
            types[key](value) if types[key]? and value

          return canvas

        it 'rectangle is drawn correctly', ->
          assertAnswer(@problem, {
            'answers':
              '12345':
                'rectangle': '(10,10)-(30,30)',
                'regions': null
          })

        it 'region is drawn correctly', ->
          assertAnswer(@problem, {
            'answers':
              '12345':
                'rectangle': null,
                'regions': '[[10,10],[30,30],[70,30],[20,30]]'
          })

        it 'mixed shapes are drawn correctly', ->
          assertAnswer(@problem, {
            'answers':'12345':
              'rectangle': '(10,10)-(30,30);(5,5)-(20,20)',
              'regions': '''[
                [[50,50],[40,40],[70,30],[50,70]],
                [[90,95],[95,95],[90,70],[70,70]]
              ]'''
          })

        it 'multiple image inputs draw answers on separate canvases', ->
          data =
            id: '67890'
            width: '400'
            height: '300'

          @problem.el.prepend _.template(imageinput_html)(data)
          assertAnswer(@problem, {
            'answers':
              '12345':
                'rectangle': null,
                'regions': '[[10,10],[30,30],[70,30],[20,30]]'
              '67890':
                'rectangle': '(10,10)-(30,30)',
                'regions': null
          })

        it 'dictionary with answers doesn\'t contain answer for current id', ->
          spyOn console, 'log'
          stubRequest({'answers':{}})
          @problem.show()
          el = $('#inputtype_12345')
          expect(el.find('canvas')).not.toExist()
          expect(console.log).toHaveBeenCalledWith('Answer is absent for image input with id=12345')

  describe 'save', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @problem.answers = 'foo=1&bar=2'

    it 'log the problem_save event', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        promise =
          always: (callable) -> callable()
      @problem.save()
      expect(Logger.log).toHaveBeenCalledWith 'problem_save', 'foo=1&bar=2'

    it 'POST to save problem', ->
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        promise =
          always: (callable) -> callable()
      @problem.save()
      expect($.postWithPrefix).toHaveBeenCalledWith '/problem/Problem1/problem_save',
          'foo=1&bar=2', jasmine.any(Function)

    it 'tests that save does not enable the submit button or change the text when submit is originally disabled', ->
      self = this
      curr_html = @problem.el.html()
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        # enableButtons should have been called at this point and the submit button should be unaffected
        expect(self.problem.submitButton).toHaveAttr('disabled')
        expect(self.problem.submitButtonLabel.text()).toBe('Submit')
        callback(success: 'correct', html: curr_html)
        promise =
          always: (callable) -> callable()
      # Expect submit to be disabled and labeled properly at the start
      expect(@problem.submitButton).toHaveAttr('disabled')
      expect(@problem.submitButtonLabel.text()).toBe('Submit')
      @problem.save()
      # Submit button should have the same state after save has completed
      expect(@problem.submitButton).toHaveAttr('disabled')
      expect(@problem.submitButtonLabel.text()).toBe('Submit')

    it 'tests that save does not disable the submit button or change the text when submit is originally enabled', ->
      self = this
      curr_html = @problem.el.html()
      spyOn($, 'postWithPrefix').and.callFake (url, answers, callback) ->
        # enableButtons should have been called at this point, and the submit button should be disabled while submitting
        expect(self.problem.submitButton).toHaveAttr('disabled')
        expect(self.problem.submitButtonLabel.text()).toBe('Submit')
        callback(success: 'correct', html: curr_html)
        promise =
          always: (callable) -> callable()
      # Expect submit to be enabled and labeled properly at the start after adding an input
      $('#input_example_1').val('test').trigger('input')
      expect(@problem.submitButton).not.toHaveAttr('disabled')
      expect(@problem.submitButtonLabel.text()).toBe('Submit')
      @problem.save()
      # Submit button should have the same state after save has completed
      expect(@problem.submitButton).not.toHaveAttr('disabled')
      expect(@problem.submitButtonLabel.text()).toBe('Submit')

  describe 'refreshMath', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      $('#input_example_1').val 'E=mc^2'
      @problem.refreshMath target: $('#input_example_1').get(0)

    it 'should queue the conversion and MathML element update', ->
      expect(MathJax.Hub.Queue).toHaveBeenCalledWith ['Text', @stubbedJax, 'E=mc^2'],
        [@problem.updateMathML, @stubbedJax, $('#input_example_1').get(0)]

  describe 'updateMathML', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @stubbedJax.root.toMathML.and.returnValue '<MathML>'

    describe 'when there is no exception', ->
      beforeEach ->
        @problem.updateMathML @stubbedJax, $('#input_example_1').get(0)

      it 'convert jax to MathML', ->
        expect($('#input_example_1_dynamath')).toHaveValue '<MathML>'

    describe 'when there is an exception', ->
      beforeEach ->
        error = new Error()
        error.restart = true
        @stubbedJax.root.toMathML.and.throwError error
        @problem.updateMathML @stubbedJax, $('#input_example_1').get(0)

      it 'should queue up the exception', ->
        expect(MathJax.Callback.After).toHaveBeenCalledWith [@problem.refreshMath, @stubbedJax], true

  describe 'refreshAnswers', ->
    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @problem.el.html '''
        <textarea class="CodeMirror" />
        <input id="input_1_1" name="input_1_1" class="schematic" value="one" />
        <input id="input_1_2" name="input_1_2" value="two" />
        <input id="input_bogus_3" name="input_bogus_3" value="three" />
        '''
      @stubSchematic = { update_value: jasmine.createSpy('schematic') }
      @stubCodeMirror = { save: jasmine.createSpy('CodeMirror') }
      $('input.schematic').get(0).schematic = @stubSchematic
      $('textarea.CodeMirror').get(0).CodeMirror = @stubCodeMirror

    it 'update each schematic', ->
      @problem.refreshAnswers()
      expect(@stubSchematic.update_value).toHaveBeenCalled()

    it 'update each code block', ->
      @problem.refreshAnswers()
      expect(@stubCodeMirror.save).toHaveBeenCalled()

  describe 'multiple JsInput in single problem', ->
    jsinput_html = readFixtures('jsinput_problem.html')

    beforeEach ->
      @problem = new Problem($('.xblock-student_view'))
      @problem.render(jsinput_html)

    it 'submit_save_waitfor should return false', ->
      $(@problem.inputs[0]).data('waitfor', ->)
      expect(@problem.submit_save_waitfor()).toEqual(false)

  describe 'Submitting an xqueue-graded problem', ->
    matlabinput_html = readFixtures('matlabinput_problem.html')

    beforeEach ->
      spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
        callback html: matlabinput_html
      jasmine.clock().install()
      @problem = new Problem($('.xblock-student_view'))
      spyOn(@problem, 'poll').and.callThrough()
      @problem.render(matlabinput_html)

    afterEach ->
      jasmine.clock().uninstall()

    it 'check that we stop polling after a fixed amount of time', ->
      expect(@problem.poll).not.toHaveBeenCalled()
      jasmine.clock().tick(1)
      time_steps = [1000, 2000, 4000, 8000, 16000, 32000]
      num_calls = 1
      for time_step in time_steps
        do (time_step) =>
          jasmine.clock().tick(time_step)
          expect(@problem.poll.calls.count()).toEqual(num_calls)
          num_calls += 1

      # jump the next step and verify that we are not still continuing to poll
      jasmine.clock().tick(64000)
      expect(@problem.poll.calls.count()).toEqual(6)

      expect($('.notification-gentle-alert .notification-message').text()).toEqual("The grading process is still running. Refresh the page to see updates.")

  describe 'codeinput problem', ->
    codeinputProblemHtml = readFixtures('codeinput_problem.html')

    beforeEach ->
      spyOn($, 'postWithPrefix').and.callFake (url, callback) ->
        callback html: codeinputProblemHtml
      @problem = new Problem($('.xblock-student_view'))
      @problem.render(codeinputProblemHtml)

    it 'has rendered with correct a11y info', ->
      CodeMirrorTextArea = $('textarea')[1]
      CodeMirrorTextAreaId = 'cm-textarea-101'

      # verify that question label has correct `for` attribute value
      expect($('.problem-group-label').attr('for')).toEqual(CodeMirrorTextAreaId)

      # verify that codemirror textarea has correct `id` attribute value
      expect($(CodeMirrorTextArea).attr('id')).toEqual(CodeMirrorTextAreaId)

      # verify that codemirror textarea has correct `aria-describedby` attribute value
      expect($(CodeMirrorTextArea).attr('aria-describedby')).toEqual('cm-editor-exit-message-101 status_101')
